// main/scene_codec.c —— 自定义 RLE 场景图解码器(逐行解码, 零堆分配)。
//
// LVGL 9 的「分块解码」绘制路径: open_cb 返回 OK 且 decoded=NULL 时,
// 绘制循环会反复调 get_area_cb 索要小块解码结果(img_decode_and_draw)。
// 我们每次解出一行, 由 LVGL 混色进 20 行的局部刷新缓冲。
// 单绘制单元(CONFIG_LV_DRAW_SW_DRAW_UNIT_CNT=1)下解码串行, 状态可用静态变量。
#include "scene_codec.h"
#include "draw/lv_image_decoder_private.h"

#include <string.h>

#define SCENE_LINE_MAX_W 240
static uint8_t     s_line_data[SCENE_LINE_MAX_W * 2];   // 一行 RGB565
static lv_draw_buf_t s_line_buf;                        // 指向 s_line_data

// ---- 当前打开的 RLE 流 ----
static uint16_t     s_w, s_h, s_npal;
static uint16_t     s_pal[256];
static const uint8_t *s_rowtab;                         // 行偏移表
static const uint8_t *s_rowdata;                        // 行数据区
static bool         s_wide;                             // true='SRL2': 行偏移 u32(大图行数据可超 64KB)

static uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool is_scene(const lv_image_dsc_t *img)
{
    // 'SRLE' = u16 行偏移(Seed Sim 场景); 'SRL2' = u32 行偏移(人生模拟器封面等大图)
    return img && img->data &&
           img->data[0] == 'S' && img->data[1] == 'R' &&
           img->data[2] == 'L' &&
           (img->data[3] == 'E' || img->data[3] == '2');
}

static void parse_header(const uint8_t *p)
{
    s_w    = rd16(p + 4);
    s_h    = rd16(p + 6);
    s_npal = rd16(p + 8);
    s_wide = (p[3] == '2');
    for (int i = 0; i < s_npal; i++) s_pal[i] = rd16(p + 10 + i * 2);
    s_rowtab = p + 10 + s_npal * 2;
    s_rowdata = s_rowtab + s_h * (s_wide ? 4 : 2);
}

static lv_result_t info_cb(lv_image_decoder_t *dec, lv_image_decoder_dsc_t *dsc,
                           lv_image_header_t *header)
{
    (void)dec;
    if (dsc->src_type != LV_IMAGE_SRC_VARIABLE) return LV_RESULT_INVALID;
    const lv_image_dsc_t *img = dsc->src;
    if (!is_scene(img)) return LV_RESULT_INVALID;

    header->magic  = LV_IMAGE_HEADER_MAGIC;
    header->cf     = LV_COLOR_FORMAT_RGB565;
    header->w      = rd16(img->data + 4);
    header->h      = rd16(img->data + 6);
    header->stride = header->w * 2;
    header->flags  = 0;
    return LV_RESULT_OK;
}

static lv_result_t open_cb(lv_image_decoder_t *dec, lv_image_decoder_dsc_t *dsc)
{
    (void)dec;
    if (dsc->src_type != LV_IMAGE_SRC_VARIABLE) return LV_RESULT_INVALID;
    const lv_image_dsc_t *img = dsc->src;
    if (!is_scene(img)) return LV_RESULT_INVALID;

    parse_header(img->data);
    // open 阶段也必须填 header(私有结构注释要求)
    dsc->header.magic  = LV_IMAGE_HEADER_MAGIC;
    dsc->header.cf     = LV_COLOR_FORMAT_RGB565;
    dsc->header.w      = s_w;
    dsc->header.h      = s_h;
    dsc->header.stride = s_w * 2;
    dsc->header.flags  = 0;
    dsc->decoded = NULL;                  // 走 get_area 逐行解码路径
    dsc->user_data = NULL;
    return LV_RESULT_OK;
}

// 解一行游程编码, 只填充 [x1..x2] 区段(缓冲从 x1 对齐)。
static void decode_row(int y, int x1, int x2)
{
    uint16_t *dst = (uint16_t *)s_line_data;
    uint32_t row_off = s_wide ? rd32(s_rowtab + (uint32_t)y * 4)
                              : rd16(s_rowtab + y * 2);
    const uint8_t *p = s_rowdata + row_off;
    int x = 0;
    while (x <= x2) {
        int cnt = *p++;
        uint8_t ci = *p++;
        int end = x + cnt;
        if (end > x2) end = x2 + 1;
        if (end > x1) {
            uint16_t c = s_pal[ci];
            int from = x > x1 ? x : x1;
            for (int i = from; i < end; i++) dst[i - x1] = c;
        }
        x += cnt;
    }
}

static lv_result_t get_area_cb(lv_image_decoder_t *dec, lv_image_decoder_dsc_t *dsc,
                               const lv_area_t *full_area, lv_area_t *decoded_area)
{
    (void)dec;
    int32_t y;
    if (decoded_area->y1 == LV_COORD_MIN) {          // 首次调用: 从第一行开始
        *decoded_area = *full_area;
        decoded_area->y2 = decoded_area->y1;
        y = decoded_area->y1;
    } else {
        y = decoded_area->y1 + 1;
        if (y > full_area->y2 || y > (int32_t)s_h - 1) return LV_RESULT_INVALID;
        decoded_area->y1 = y;
        decoded_area->y2 = y;
    }
    if (y > (int32_t)s_h - 1) return LV_RESULT_INVALID;

    decode_row(y, decoded_area->x1, decoded_area->x2);
    dsc->decoded = &s_line_buf;                      // 告诉绘制循环数据在哪
    return LV_RESULT_OK;
}

static void close_cb(lv_image_decoder_t *dec, lv_image_decoder_dsc_t *dsc)
{
    (void)dec;
    dsc->decoded = NULL;                             // 静态缓冲, 无需释放
}

void scene_codec_init(void)
{
    static bool inited;
    if (inited) return;
    inited = true;

    lv_draw_buf_init(&s_line_buf, SCENE_LINE_MAX_W, 1, LV_COLOR_FORMAT_RGB565,
                     sizeof(s_line_data), s_line_data, sizeof(s_line_data));

    lv_image_decoder_t *dec = lv_image_decoder_create();
    lv_image_decoder_set_info_cb(dec, info_cb);
    lv_image_decoder_set_open_cb(dec, open_cb);
    lv_image_decoder_set_get_area_cb(dec, get_area_cb);
    lv_image_decoder_set_close_cb(dec, close_cb);
}

void scene_dsc_init(lv_image_dsc_t *d, const uint8_t *rle)
{
    memset(d, 0, sizeof(*d));
    d->header.magic  = LV_IMAGE_HEADER_MAGIC;
    d->header.cf     = LV_COLOR_FORMAT_RGB565;
    d->header.w      = rd16(rle + 4);
    d->header.h      = rd16(rle + 6);
    d->header.stride = d->header.w * 2;
    d->data          = rle;
}

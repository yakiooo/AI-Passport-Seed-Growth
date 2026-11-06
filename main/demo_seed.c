// main/demo_seed.c —— 种子生长模拟器:链式二选一叙事游戏(UI 精致版)。
//
// 状态机: HOME(开始) → PLAY(游戏) → END(结局) → HOME; HOME ↔ ACH(图鉴);
//         PLAY → MENU(暂停菜单:继续/返回主页/重置进度)。
// 并发: 按键回调/LVGL 定时器只做模型运算与 UI 刷新; 音频与 NVS 写入交给工作任务。
// 素材: 64x64 RGB565 常量数组(Flash 内存映射), 4 帧摇摆动画由定时器切换。
// 视觉: 深蓝灰底 #1A1A2E + 卡片 #2A2A3E, 青/蓝强调, 圆角卡片, 呼吸/漂浮动画。
#include "demo.h"
#include "seed_story.h"
#include "seed_save.h"
#include "seed_assets.h"
#include "scene_codec.h"
#include "scene_data.h"
#include "bsp_audio.h"
#include "bsp_display.h"
#include "lvgl.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include <stdio.h>
#include <string.h>

LV_FONT_DECLARE(seed_font_16);

static const char *TAG = "seed";

// ------- 色彩系统(UI 规范) -------
#define SG_BG      0x1A1A2E       // 主背景
#define SG_BG2     0x242438       // 次级背景
#define SG_CARD    0x2A2A3E       // 卡片
#define SG_BORDER  0x3A3A4E       // 边框
#define SG_TXT     0xFAFAFA       // 主文字
#define SG_MUTED   0xA1A1AA       // 次级文字
#define SG_DIM     0x52525B       // 禁用文字
#define SG_CYAN    0x06B6D4       // 主强调
#define SG_BLUE    0x3B82F6       // 次强调(UP)
#define SG_GREEN   0x10B981       // 成功
#define SG_ORANGE  0xF59E0B       // 警告(DOWN)
#define SG_RED     0xEF4444       // 危险
#define SG_GOLD    0xFFD700       // 隐藏结局

// ---------------- 工作任务(音效/NVS) ----------------
typedef enum { MSG_BEEP = 0, MSG_SAVE, MSG_QUIT } seed_msg_type_t;
typedef struct { seed_msg_type_t type; int arg; } seed_msg_t;

enum { BP_CLICK = 0, BP_SELECT, BP_WHOOSH, BP_END, BP_UNLOCK, BP_DENY, BP_COUNT };
typedef struct { uint16_t freq; uint16_t ms; } beep_note_t;
static const beep_note_t BEEPS[][4] = {
    [BP_CLICK]  = { {1000, 40},  {0, 0},     {0, 0},     {0, 0} },
    [BP_SELECT] = { {660, 70},   {880, 70},  {1100, 90}, {0, 0} },
    [BP_WHOOSH] = { {420, 70},   {330, 70},  {260, 80}, {0, 0} },
    [BP_END]    = { {523, 150},  {659, 150}, {784, 150}, {1047, 280} },
    [BP_UNLOCK] = { {880, 110},  {1175, 240},{0, 0},     {0, 0} },
    [BP_DENY]   = { {330, 70},   {262, 100}, {0, 0},     {0, 0} },
};

#define PCM_RATE      16000
#define PCM_MAX_NOTE  3200               // 200ms 上限
static int16_t s_pcm[PCM_MAX_NOTE];

// LVGL 用的是自带堆(CONFIG_LV_MEM_SIZE_KILOBYTES), 缩放绘制的临时缓冲、渐变色表
// 都从这里申请; 一旦申请失败会触发 LV_ASSERT_MALLOC 死循环(表现为看门狗 + 0xdeadc0de)。
// 这里定期打占用, 便于定位是哪一屏把堆吃满。
static void mem_log(const char *where)
{
    lv_mem_monitor_t m;
    lv_mem_monitor(&m);
    ESP_LOGI(TAG, "LVGL 堆[%s] 总%u 用%u%% 空闲%u 最大块%u 碎片%u%%",
             where, (unsigned)m.total_size, (unsigned)m.used_pct,
             (unsigned)m.free_size, (unsigned)m.free_biggest_size,
             (unsigned)m.frag_pct);
}

static QueueHandle_t s_queue;
static TaskHandle_t  s_worker;
static seed_save_t   s_save;   // 保存状态(worker 快照也要访问)

static void play_beep(int id)
{
    if (s_save.volume == SEED_VOL_MUTE) return;
    const beep_note_t *notes = BEEPS[id];
    bsp_audio_set_format(PCM_RATE, 16, 1);
    bsp_audio_set_volume(s_save.volume == SEED_VOL_LOW ? 22 : 55);
    for (int n = 0; n < 4 && notes[n].ms > 0; n++) {
        int samples = (int)notes[n].ms * PCM_RATE / 1000;
        if (samples > PCM_MAX_NOTE) samples = PCM_MAX_NOTE;
        for (int i = 0; i < samples; i++) {
            s_pcm[i] = (((int64_t)i * notes[n].freq / PCM_RATE) & 1) ? 11000 : -11000;
        }
        if (bsp_audio_write(s_pcm, (size_t)samples * 2) != ESP_OK) return;
    }
}

static void seed_worker(void *arg)
{
    (void)arg;
    seed_msg_t msg;
    for (;;) {
        if (xQueueReceive(s_queue, &msg, portMAX_DELAY) != pdTRUE) continue;
        if (msg.type == MSG_BEEP) {
            play_beep(msg.arg);
        } else if (msg.type == MSG_SAVE) {
            // s_save 只被 LVGL 锁持有者修改, 快照前先拿锁。
            if (bsp_lvgl_lock(1000)) {
                seed_save_t snap = s_save;
                bsp_lvgl_unlock();
                seed_save_store(&snap);
            }
        }
        if (msg.type == MSG_QUIT) {
            s_worker = NULL;
            vTaskDelete(NULL);
        }
    }
}

static void enqueue(seed_msg_type_t type, int arg)
{
    if (!s_queue) return;
    seed_msg_t msg = { type, arg };
    xQueueSend(s_queue, &msg, 0);
}

// ---------------- 游戏状态(仅 LVGL 锁上下文访问) ----------------
typedef enum { SG_HOME = 0, SG_ACH, SG_PLAY, SG_END, SG_MENU } sg_state_t;

static sg_state_t  s_state = SG_HOME;
static int         s_node = 1;                 // 当前节点 1..32
static int16_t     s_pending = -1000;          // 过渡中的去向(-1000=无过渡)
static bool        s_end_new;                  // 当前结局是否为新解锁
static int         s_end_id;

static int    s_home_sel, s_home_count;        // 首页焦点
static int    s_grid;                          // 图鉴光标 0..13(13=返回格)
static bool   s_detail_open;
static int    s_menu_sel;                      // 暂停菜单焦点 0..2
static bool   s_menu_confirm;                  // 重置进度二次确认

static lv_obj_t   *s_scr;
static lv_obj_t   *s_form_img;                 // PLAY/END 的大形态图
static lv_image_dsc_t s_dsc[4];                // 4 帧描述符
static lv_obj_t   *s_desc_l, *s_prog_l, *s_opt_l[2];
static lv_obj_t   *s_opt_box[2];
static lv_obj_t   *s_btns[4];                  // 首页按钮(主/重来/历史/音量)
static int         s_home_role[4];             // 各按钮的职责
enum { HR_START = 0, HR_NEW, HR_ACH, HR_VOL };
static lv_obj_t   *s_cells[SEED_ENDING_COUNT + 1];  // 图鉴 13 结局格
static lv_obj_t   *s_cell_back;                // 返回格
static lv_obj_t   *s_cell_img[SEED_ENDING_COUNT + 1];
static lv_image_dsc_t s_cell_dsc[SEED_ENDING_COUNT + 1];
static lv_obj_t   *s_detail, *s_home_seed, *s_menu_card;
static lv_obj_t   *s_menu_btns[3];             // 暂停菜单按钮(独立持有)
static lv_obj_t   *s_hint_l, *s_flash;
static lv_timer_t *s_timer;
// PLAY/END 的场景背景(RLE 逐行解码)。
// 两个槽轮换使用: 换幕时写到另一个槽, 再 set_src 到新指针。若原地改同一个
// lv_image_dsc_t 的内容, src 指针不变、LVGL 判定无变化就不会重绘, 画面会卡在第一幕。
static lv_image_dsc_t s_bg_dsc[2];
static int            s_bg_slot;                   // 当前生效的槽(0/1)
static lv_obj_t      *s_bg_img;                    // 背景图对象(换幕时要更新 src)
static int16_t        s_bg_form = -1;              // 当前背景对应的形态, -1 = 未设置

// 形态索引 -> 场景背景(SCENE_RLE 下标 0..31)。无对应场景的形态用最贴近的。
static const uint8_t FORM_TO_SCENE[32] = {
    0, 1, 2, 3, 4, 5, 6, 7,                    // seed..scorched 一一对应
    16, 17, 9, 15, 20, 10, 11, 22,             // windowsill corner overwatered just_right
                                               // sprout withered(浇水不足) rained flooded
    13, 14, 24, 25, 17, 18, 21, 23,            // blown stepped bloom fruit
                                               // corner_grow(角落) rotten(水淹) seedling rooted(新土)
    26, 27, 20, 28, 29, 27, 30, 31,            // eaten_by_bug eaten_by_bird butterfly(花丛)
                                               // bird_egg hatched flying(黎明天空) picked vase
};

static char s_buf1[192], s_buf2[64];           // 公共文本缓冲(避免栈上大缓冲)

// ---------------- 小工具 ----------------
static lv_obj_t *make_label(lv_obj_t *parent, int x, int y, int w,
                            const char *txt, uint32_t color, lv_align_t align)
{
    lv_obj_t *l = lv_label_create(parent);
    lv_label_set_text(l, txt);
    lv_obj_set_style_text_color(l, lv_color_hex(color), 0);
    lv_obj_set_style_text_font(l, &seed_font_16, 0);
    if (w > 0) {
        lv_obj_set_width(l, w);
        lv_label_set_long_mode(l, LV_LABEL_LONG_WRAP);
        lv_obj_set_style_text_align(l, LV_TEXT_ALIGN_CENTER, 0);
    }
    if (align == LV_ALIGN_DEFAULT) { lv_obj_set_pos(l, x, y); }
    else { lv_obj_align(l, align, x, y); }
    return l;
}

static lv_obj_t *make_card(lv_obj_t *parent, int x, int y, int w, int h,
                           uint32_t bg, int radius)
{
    lv_obj_t *c = lv_obj_create(parent);
    lv_obj_set_pos(c, x, y);
    lv_obj_set_size(c, w, h);
    // 关键: lv_obj 默认主题带内边距, 子控件坐标会整体右移/下移
    // (详情弹窗文本偏右就是这个原因)。所有自绘卡片一律清零。
    lv_obj_set_style_pad_all(c, 0, 0);
    lv_obj_set_style_bg_color(c, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(c, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(c, 0, 0);
    lv_obj_set_style_radius(c, radius, 0);
    lv_obj_set_scrollbar_mode(c, LV_SCROLLBAR_MODE_OFF);
    return c;
}

// 柔和投影(卡片阴影规范: 0 4px 12px 黑 30%)
static void card_shadow(lv_obj_t *c)
{
    lv_obj_set_style_shadow_color(c, lv_color_hex(0x000000), 0);
    lv_obj_set_style_shadow_width(c, 12, 0);
    lv_obj_set_style_shadow_spread(c, 1, 0);
    lv_obj_set_style_shadow_ofs_y(c, 4, 0);
    lv_obj_set_style_shadow_opa(c, LV_OPA_30, 0);
}

// 选中发光(对应色 0 0 16px)
static void glow(lv_obj_t *c, uint32_t color, int width)
{
    lv_obj_set_style_shadow_color(c, lv_color_hex(color), 0);
    lv_obj_set_style_shadow_width(c, width, 0);
    lv_obj_set_style_shadow_spread(c, 2, 0);
    lv_obj_set_style_shadow_opa(c, LV_OPA_40, 0);
}

static void no_glow(lv_obj_t *c)
{
    lv_obj_set_style_shadow_width(c, 0, 0);
    lv_obj_set_style_shadow_opa(c, LV_OPA_TRANSP, 0);
}

static void set_focus_ring(lv_obj_t *card, bool on, uint32_t color)
{
    lv_obj_set_style_border_width(card, on ? 2 : 1, 0);
    lv_obj_set_style_border_color(card,
        lv_color_hex(on ? color : SG_BORDER), 0);
    lv_obj_set_style_border_opa(card, LV_OPA_COVER, 0);
    if (on) glow(card, color, 16);
    else    no_glow(card);
}

static void ensure_worker(void)
{
    if (s_queue) return;
    s_queue = xQueueCreate(8, sizeof(seed_msg_t));
    if (s_queue && xTaskCreate(seed_worker, "seed_w", 3072, NULL, 4, &s_worker) != pdPASS) {
        vQueueDelete(s_queue);
        s_queue = NULL;
    }
}

// 定时器: 4 帧摇摆/开合动画
static void frame_cb(lv_timer_t *t)
{
    (void)t;
    static uint8_t idx;
    static uint16_t ticks;
    idx = (idx + 1) & 3;
    if (s_form_img) lv_image_set_src(s_form_img, &s_dsc[idx]);
    if (s_home_seed) lv_image_set_src(s_home_seed, &s_dsc[idx]);
    if (++ticks >= 15) { ticks = 0; mem_log("周期"); }   // 约 6 秒一次
}

// 呼吸动画: 缩放 512 -> 526 (2s 循环, 约 ±1.4%)
static void breath_anim(lv_obj_t *img)
{
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, img);
    lv_anim_set_exec_cb(&a, (lv_anim_exec_xcb_t)lv_image_set_scale);
    lv_anim_set_values(&a, 512, 526);
    lv_anim_set_duration(&a, 1000);
    lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_reverse_time(&a, lv_anim_get_time(&a));
    lv_anim_start(&a);
}

// 白色闪光(节点过渡 100ms)
// 注意: lv_obj_set_style_opa 是三参数, 而动画回调只传 (var, value)。
// 不能直接强转当回调 —— 第三个 selector 参数会读到寄存器里的垃圾值。
static void flash_exec(void *var, int32_t v)
{
    lv_obj_set_style_opa((lv_obj_t *)var, (lv_opa_t)v, 0);
}

static void flash_done(lv_anim_t *a)
{
    lv_obj_t *f = (lv_obj_t *)a->var;
    if (f == s_flash) s_flash = NULL;
    lv_obj_delete(f);
}

static void play_flash(void)
{
    if (s_flash) return;
    lv_obj_t *f = lv_obj_create(s_scr);
    lv_obj_set_style_pad_all(f, 0, 0);
    lv_obj_set_pos(f, 0, 0);
    lv_obj_set_size(f, 240, 320);
    lv_obj_set_style_bg_color(f, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(f, LV_OPA_40, 0);
    lv_obj_set_style_border_width(f, 0, 0);
    lv_obj_set_style_radius(f, 0, 0);
    lv_obj_set_scrollbar_mode(f, LV_SCROLLBAR_MODE_OFF);
    lv_obj_clear_flag(f, LV_OBJ_FLAG_CLICKABLE);
    s_flash = f;

    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, f);
    lv_anim_set_exec_cb(&a, flash_exec);
    lv_anim_set_values(&a, LV_OPA_40, LV_OPA_TRANSP);
    lv_anim_set_duration(&a, 120);
    lv_anim_set_ready_cb(&a, flash_done);
    lv_anim_start(&a);
}

// ---------------- 开始界面(夜晚花园场景) ----------------
#define HR_COLOR(r) ((r) == HR_START ? SG_CYAN : SG_MUTED)

static const char *vol_label(void)
{
    // 字体子集无"低"字, 用"小"表示低档
    return s_save.volume == SEED_VOL_HIGH ? "音:高"
         : s_save.volume == SEED_VOL_LOW  ? "音:小" : "静音";
}

static void home_refresh(void)
{
    for (int i = 0; i < s_home_count; i++) {
        set_focus_ring(s_btns[i], i == s_home_sel, HR_COLOR(s_home_role[i]));
        if (i == s_home_sel && s_home_role[i] == HR_START)
            glow(s_btns[i], SG_CYAN, 20);
        if (s_home_role[i] == HR_VOL) {
            lv_obj_t *l = lv_obj_get_child(s_btns[i], 0);
            lv_label_set_text(l, vol_label());
        }
    }
}

// ---------------- 开始界面(封面 4 帧动画) ----------------
// 封面是一张 240x320 的 4 帧像素动画(用户提供 GIF 转制, RLE 内嵌)。
// frame_cb 每 400ms 切一帧(与原 GIF 帧延时一致), 走 s_home_seed + s_dsc 通道。
static void home_build(void)
{
    s_state = SG_HOME;
    s_form_img = NULL;         // 旧 PLAY/END 屏将被 auto_del, 悬空指针必须清掉
    s_bg_img = NULL;
    s_bg_form = -1;
    s_menu_card = NULL;        // 暂停遮罩也随旧屏一起销毁
    for (int i = 0; i < 3; i++) s_menu_btns[i] = NULL;

    s_scr = lv_obj_create(NULL);
    lv_obj_set_style_pad_all(s_scr, 0, 0);     // 屏幕也清内边距, 坐标才与设计一致
    lv_obj_set_style_bg_color(s_scr, lv_color_hex(0x0F2440), 0);
    lv_obj_set_style_bg_opa(s_scr, LV_OPA_COVER, 0);

    // 封面帧动画(帧数据在 Flash, 解码只占一行 RAM)
    for (int f = 0; f < COVER_FRAME_COUNT; f++)
        scene_dsc_init(&s_dsc[f], COVER_RLE[f]);
    s_home_seed = lv_image_create(s_scr);
    lv_image_set_src(s_home_seed, &s_dsc[0]);
    lv_obj_set_pos(s_home_seed, 0, 0);
    lv_obj_clear_flag(s_home_seed, LV_OBJ_FLAG_CLICKABLE);

    // 统计行(封面自带标题, 这里只补进度信息)。版本号便于确认刷机是否生效
    int unlocked = 0;
    for (int i = 1; i <= SEED_ENDING_COUNT; i++)
        if (seed_ending_unlocked(&s_save, i)) unlocked++;
    snprintf(s_buf1, sizeof(s_buf1), "v8  已解锁 %d / %d   第 %lu 局",
             unlocked, SEED_ENDING_COUNT, (unsigned long)s_save.play_count);
    make_label(s_scr, 0, 68, 240, s_buf1, SG_MUTED, LV_ALIGN_DEFAULT);

    // --- 按钮层(主按钮 + 重来/历史/音量) ---
    bool has_cont = (s_save.last_node > 0 && s_save.last_node <= SEED_NODE_COUNT);
    int n = 0;
    int ys[4], hs[4];
    ys[n] = 214; hs[n] = 44; s_home_role[n++] = HR_START;
    if (has_cont) {
        ys[n] = 264; hs[n] = 38; s_home_role[n++] = HR_NEW;
        ys[n] = 264; hs[n] = 38; s_home_role[n++] = HR_ACH;
    } else {
        ys[n] = 264; hs[n] = 38; s_home_role[n++] = HR_ACH;
    }
    ys[n] = 264; hs[n] = 38; s_home_role[n++] = HR_VOL;
    s_home_count = n;

    for (int i = 0; i < n; i++) {
        int role = s_home_role[i];
        lv_obj_t *b;
        if (role == HR_START) {
            b = make_card(s_scr, 20, ys[i], 200, hs[i], SG_CARD, 16);
            lv_obj_set_style_bg_grad_dir(b, LV_GRAD_DIR_VER, 0);
            lv_obj_set_style_bg_color(b, lv_color_hex(SG_CYAN), 0);
            lv_obj_set_style_bg_grad_color(b, lv_color_hex(SG_BLUE), 0);
            lv_obj_set_style_bg_opa(b, LV_OPA_COVER, 0);
            make_label(b, 0, 0, 0, has_cont ? "继续游戏" : "开始游戏",
                       SG_TXT, LV_ALIGN_CENTER);
        } else {
            int x = (n == 4) ? 20 + (i - 1) * 69      // 62 宽 + 7 间距
                             : 20 + (i - 1) * 104;    // 96 宽 + 8 间距
            int w = (n == 4) ? 62 : 96;
            b = make_card(s_scr, x, ys[i], w, hs[i], SG_BG2, 12);
            lv_obj_set_style_bg_opa(b, LV_OPA_60, 0);
            lv_obj_set_style_border_width(b, 1, 0);
            lv_obj_set_style_border_color(b, lv_color_hex(SG_BORDER), 0);
            const char *txt = (role == HR_NEW) ? "重来" :
                              (role == HR_ACH) ? "历史" : vol_label();
            make_label(b, 0, 0, 0, txt, SG_MUTED, LV_ALIGN_CENTER);
        }
        card_shadow(b);
        s_btns[i] = b;
    }

    home_refresh();
    lv_screen_load_anim(s_scr, LV_SCR_LOAD_ANIM_FADE_IN, 250, 0, true);
}

// ---------------- 成就界面(3 列网格, 逐行居中) ----------------
#define ACH_CW   64      // 格宽
#define ACH_CH   42      // 格高
#define ACH_CY   58      // 行起点
#define ACH_GX   8
#define ACH_GY   4

// 每行独立水平居中: 13 个结局 -> 前 4 行各 3 个, 第 5 行 1 个(也居中)。
static void ach_cell_pos(int idx, int *x, int *y)
{
    int col = idx % 3;
    int row = idx / 3;
    int row_items = (row < SEED_ENDING_COUNT / 3)
                        ? 3
                        : SEED_ENDING_COUNT - row * 3;
    int row_w = row_items * ACH_CW + (row_items - 1) * ACH_GX;
    *x = (240 - row_w) / 2 + col * (ACH_CW + ACH_GX);
    *y = ACH_CY + row * (ACH_CH + ACH_GY);
}

static void ach_refresh(void)
{
    for (int i = 1; i <= SEED_ENDING_COUNT; i++) {
        bool hidden = (i == SEED_HIDDEN_ENDING);
        set_focus_ring(s_cells[i], s_grid == i - 1 && !s_detail_open,
                       hidden ? SG_GOLD : SEED_ENDINGS[i].color);
    }
    set_focus_ring(s_cell_back, s_grid == SEED_ENDING_COUNT, SG_CYAN);
    if (s_hint_l) {
        lv_label_set_text(s_hint_l, "UP/DOWN 移动  确认 查看");
        lv_obj_set_style_text_color(s_hint_l, lv_color_hex(SG_MUTED), 0);
    }
}

static void ach_build(void)
{
    s_state = SG_ACH;
    s_detail_open = false;
    s_home_seed = NULL;
    s_bg_img = NULL;           // 图鉴屏没有场景背景
    s_bg_form = -1;
    s_scr = lv_obj_create(NULL);
    lv_obj_set_style_pad_all(s_scr, 0, 0);
    lv_obj_set_style_bg_color(s_scr, lv_color_hex(SG_BG), 0);
    lv_obj_set_style_bg_opa(s_scr, LV_OPA_COVER, 0);

    make_label(s_scr, 0, 8, 0, "结局图鉴", SG_TXT, LV_ALIGN_TOP_MID);

    int unlocked = 0;
    for (int i = 1; i <= SEED_ENDING_COUNT; i++) {
        if (seed_ending_unlocked(&s_save, i)) unlocked++;
    }
    snprintf(s_buf1, sizeof(s_buf1), "已解锁 %d / %d", unlocked, SEED_ENDING_COUNT);
    make_label(s_scr, 0, 32, 240, s_buf1, SG_MUTED, LV_ALIGN_DEFAULT);

    for (int i = 1; i <= SEED_ENDING_COUNT; i++) {
        bool unlock = seed_ending_unlocked(&s_save, i);
        bool hidden = (i == SEED_HIDDEN_ENDING);
        int x, y;
        ach_cell_pos(i - 1, &x, &y);
        lv_obj_t *cell = make_card(s_scr, x, y, ACH_CW, ACH_CH, SG_CARD, 8);
        s_cells[i] = cell;

        if (unlock) {
            seed_asset_fill_dsc(&s_cell_dsc[i], SEED_ENDINGS[i].form, 0);
            lv_obj_t *img = lv_image_create(cell);
            lv_image_set_src(img, &s_cell_dsc[i]);
            lv_image_set_scale(img, 117);          // 48 -> 22px 缩略图
            lv_image_set_pivot(img, 0, 0);         // 左上角锚定, 好排格子
            lv_obj_set_pos(img, 21, 2);
            s_cell_img[i] = img;
            snprintf(s_buf2, sizeof(s_buf2), "%s", SEED_ENDINGS[i].name);
            make_label(cell, 0, 25, 0, s_buf2,
                       hidden ? SG_GOLD : SG_TXT, LV_ALIGN_TOP_MID);
        } else {
            s_cell_img[i] = NULL;
            make_label(cell, 0, 3, 0, hidden ? "隐藏" : "？？？",
                       hidden ? SG_GOLD : SG_DIM, LV_ALIGN_TOP_MID);
            if (hidden) {
                make_label(cell, 0, 24, 0, "集齐 12 个", SG_DIM, LV_ALIGN_TOP_MID);
            }
            lv_obj_set_style_opa(cell, LV_OPA_40, 0);
        }
    }

    // 返回条(网格下方居中的长条按钮)
    int by = ACH_CY + ((SEED_ENDING_COUNT + 2) / 3) * (ACH_CH + ACH_GY) + 4;
    s_cell_back = make_card(s_scr, 70, by, 100, 26, SG_CARD, 13);
    make_label(s_cell_back, 0, 0, 0, "返回主页", SG_MUTED, LV_ALIGN_CENTER);

    ach_refresh();
    lv_screen_load_anim(s_scr, LV_SCR_LOAD_ANIM_FADE_IN, 250, 0, true);
}

static void detail_open(int eid)
{
    if (s_detail) return;
    s_detail_open = true;

    lv_obj_t *dim = lv_obj_create(s_scr);
    lv_obj_set_style_pad_all(dim, 0, 0);
    lv_obj_set_style_bg_color(dim, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(dim, LV_OPA_70, 0);
    lv_obj_set_style_border_width(dim, 0, 0);
    lv_obj_set_style_radius(dim, 0, 0);
    lv_obj_set_pos(dim, 0, 0);
    lv_obj_set_size(dim, 240, 320);
    lv_obj_set_scrollbar_mode(dim, LV_SCROLLBAR_MODE_OFF);
    s_detail = dim;

    lv_obj_t *card = make_card(dim, 12, 36, 216, 248, SG_CARD, 12);
    lv_obj_set_style_border_width(card, 2, 0);
    lv_obj_set_style_border_color(card, lv_color_hex(SEED_ENDINGS[eid].color), 0);
    card_shadow(card);

    snprintf(s_buf1, sizeof(s_buf1), "%s", SEED_ENDINGS[eid].name);
    make_label(card, 0, 8, 0, s_buf1, SEED_ENDINGS[eid].color, LV_ALIGN_TOP_MID);

    static lv_image_dsc_t dsc;
    seed_asset_fill_dsc(&dsc, SEED_ENDINGS[eid].form, 0);
    lv_obj_t *img = lv_image_create(card);
    lv_image_set_src(img, &dsc);
    lv_image_set_scale(img, 341);                 // 48 -> 64px
    lv_obj_align(img, LV_ALIGN_TOP_MID, 0, 28);

    snprintf(s_buf2, sizeof(s_buf2), "第 %u 次游玩解锁",
             (unsigned)s_save.unlock_play[eid]);
    make_label(card, 0, 100, 0, s_buf2, SG_MUTED, LV_ALIGN_TOP_MID);
    make_label(card, 12, 122, 192, SEED_ENDINGS[eid].story, SG_TXT,
               LV_ALIGN_DEFAULT);
    make_label(card, 0, 222, 0, "按 确认 关闭", SG_DIM, LV_ALIGN_TOP_MID);
}

static void detail_close(void)
{
    if (s_detail) {
        lv_obj_delete(s_detail);
        s_detail = NULL;
    }
    s_detail_open = false;
}

// ---------------- 游戏进行 & 结局 ----------------
static void form_set(uint8_t form)
{
    for (int f = 0; f < 4; f++) seed_asset_fill_dsc(&s_dsc[f], form, f);
    if (s_form_img) lv_image_set_src(s_form_img, &s_dsc[0]);
}

// 切换场景背景到某个形态对应的画面。
// 用双槽轮换换 src 指针; 同时手动 invalidate —— set_src 对同尺寸图片
// 不保证触发重绘(尺寸没变), 这正是"背景不换"的第二层原因。
// 每次切换打一条日志, 便于在 monitor 里直接确认换幕是否执行。
static void scene_bg_set(uint8_t form)
{
    if (!s_bg_img) return;
    if ((int16_t)form == s_bg_form) return;

    uint8_t scene = FORM_TO_SCENE[form];
    s_bg_slot ^= 1;
    scene_dsc_init(&s_bg_dsc[s_bg_slot], SCENE_RLE[scene]);
    lv_image_set_src(s_bg_img, &s_bg_dsc[s_bg_slot]);
    lv_obj_invalidate(s_bg_img);
    s_bg_form = (int16_t)form;
    ESP_LOGI(TAG, "bg -> scene %02d (node %d form %d)", scene, s_node, form);
}

static void play_refresh(void)
{
    const seed_node_t *n = &SEED_NODES[s_node];
    form_set(n->form);
    scene_bg_set(n->form);            // 换幕必须换场景, 否则整局停在第一幕
    snprintf(s_buf1, sizeof(s_buf1), "第 %d / %d 幕", s_node, SEED_NODE_COUNT);
    lv_label_set_text(s_prog_l, s_buf1);
    lv_label_set_text(s_desc_l, n->desc);
    lv_label_set_text(s_opt_l[0], n->opt_up);
    lv_label_set_text(s_opt_l[1], n->opt_down);
}

static void play_build(int node)
{
    s_state = SG_PLAY;
    s_node = node;
    s_home_seed = NULL;
    s_scr = lv_obj_create(NULL);
    lv_obj_set_style_pad_all(s_scr, 0, 0);
    lv_obj_set_style_bg_color(s_scr, lv_color_hex(SG_BG), 0);
    lv_obj_set_style_bg_opa(s_scr, LV_OPA_COVER, 0);

    // 场景背景: 节点对应的一幅 240x320 RLE 图(逐行解码, RAM 只占一行)。
    // 必须第一个创建, 后续 HUD/形态图才会盖在它上面。
    s_bg_form = -1;
    s_bg_slot = 1;                         // 使首次切换落到槽 0
    s_bg_img = lv_image_create(s_scr);
    lv_obj_set_pos(s_bg_img, 0, 0);
    lv_obj_clear_flag(s_bg_img, LV_OBJ_FLAG_CLICKABLE);
    scene_bg_set(SEED_NODES[node].form);   // src 在这里真正赋值

    // 顶部 HUD 暗条: 场景天色有亮有暗, 压一层保证文字可读
    lv_obj_t *top = make_card(s_scr, 0, 0, 240, 54, 0x000000, 0);
    lv_obj_set_style_bg_opa(top, LV_OPA_50, 0);
    (void)top;

    s_prog_l = make_label(s_scr, 12, 8, 100, "", SG_MUTED, LV_ALIGN_DEFAULT);
    s_desc_l = make_label(s_scr, 12, 28, 216, "", SG_TXT, LV_ALIGN_DEFAULT);
    lv_obj_set_style_text_align(s_desc_l, LV_TEXT_ALIGN_CENTER, 0);

    // 选项区暗条(在形态图之下, 选项框之上不再垫)
    lv_obj_t *bot = make_card(s_scr, 0, 188, 240, 132, 0x000000, 0);
    lv_obj_set_style_bg_opa(bot, LV_OPA_50, 0);
    (void)bot;

    s_form_img = lv_image_create(s_scr);
    // 场景里土丘中心约 (120,194); 96px 渲染框中心放在 (120,178)
    lv_obj_align(s_form_img, LV_ALIGN_CENTER, 0, 18);
    lv_image_set_scale(s_form_img, 512);          // 48 -> 96px
    breath_anim(s_form_img);

    // 选项区: UP(蓝) / DOWN(橙) 20% 透明底 + 2px 边框
    const char *keys[2] = { "UP", "DOWN" };
    for (int i = 0; i < 2; i++) {
        lv_obj_t *box = make_card(s_scr, i ? 126 : 10, 196, 104, 84,
                                  i ? SG_ORANGE : SG_BLUE, 12);
        lv_obj_set_style_bg_opa(box, LV_OPA_20, 0);
        lv_obj_set_style_border_width(box, 2, 0);
        lv_obj_set_style_border_color(box,
            lv_color_hex(i ? SG_ORANGE : SG_BLUE), 0);
        card_shadow(box);
        s_opt_box[i] = box;
        make_label(box, 0, 8, 0, keys[i], i ? SG_ORANGE : SG_BLUE,
                   LV_ALIGN_TOP_MID);
        s_opt_l[i] = make_label(box, 4, 34, 96, "", SG_TXT, LV_ALIGN_TOP_MID);
    }

    make_label(s_scr, 0, 296, 240, "OK 菜单  长按返回", SG_MUTED,
               LV_ALIGN_DEFAULT);

    play_refresh();
    lv_screen_load_anim(s_scr, LV_SCR_LOAD_ANIM_FADE_IN, 250, 0, true);
}

static void end_build(int eid, bool is_new)
{
    s_state = SG_END;
    s_end_id = eid;
    s_end_new = is_new;
    s_home_seed = NULL;
    const seed_ending_t *e = &SEED_ENDINGS[eid];
    s_scr = lv_obj_create(NULL);
    lv_obj_set_style_pad_all(s_scr, 0, 0);
    lv_obj_set_style_bg_color(s_scr, lv_color_hex(SG_BG), 0);
    lv_obj_set_style_bg_opa(s_scr, LV_OPA_COVER, 0);

    // 场景背景: 结局对应形态的场景图
    s_bg_form = -1;
    s_bg_slot = 1;
    s_bg_img = lv_image_create(s_scr);
    lv_obj_set_pos(s_bg_img, 0, 0);
    lv_obj_clear_flag(s_bg_img, LV_OBJ_FLAG_CLICKABLE);
    scene_bg_set(e->form);

    s_form_img = lv_image_create(s_scr);
    // 128px 渲染框中心落在 (120,100)
    lv_obj_align(s_form_img, LV_ALIGN_CENTER, 0, -60);
    lv_image_set_scale(s_form_img, 683);          // 48 -> 128px
    form_set(e->form);
    breath_anim(s_form_img);

    // 底部暗条: 结局名与故事文字压在场景上, 需要可读底
    lv_obj_t *bot = make_card(s_scr, 0, 156, 240, 164, 0x000000, 0);
    lv_obj_set_style_bg_opa(bot, LV_OPA_60, 0);
    (void)bot;

    make_label(s_scr, 0, 170, 240, e->name, e->color, LV_ALIGN_DEFAULT);

    make_label(s_scr, 12, 198, 216, e->story, SG_TXT, LV_ALIGN_DEFAULT);

    if (is_new) {
        make_label(s_scr, 0, 278, 240, "已解锁新结局!", SG_GOLD,
                   LV_ALIGN_DEFAULT);
    }
    make_label(s_scr, 0, 300, 240, "按 确认 回到开始", SG_MUTED, LV_ALIGN_DEFAULT);
    lv_screen_load_anim(s_scr, LV_SCR_LOAD_ANIM_FADE_IN, 250, 0, true);
}

// ---------------- 暂停菜单 ----------------
static void menu_item_refresh(void)
{
    static const char *TXT[3] = { "继续游戏", "返回主页", "重置进度" };
    static const uint32_t COL[3] = { SG_CYAN, SG_MUTED, SG_RED };
    for (int i = 0; i < 3; i++) {
        lv_obj_t *btn = s_menu_btns[i];
        if (!btn) continue;
        set_focus_ring(btn, s_menu_sel == i, COL[i]);
        lv_obj_t *l = lv_obj_get_child(btn, 0);
        if (i == 2 && s_menu_confirm) {
            lv_label_set_text(l, "确认重置?");
        } else {
            lv_label_set_text(l, TXT[i]);
        }
    }
}

static void menu_open(void)
{
    if (s_menu_card) return;
    s_state = SG_MENU;
    s_menu_sel = 0;
    s_menu_confirm = false;

    lv_obj_t *dim = lv_obj_create(s_scr);
    lv_obj_set_style_pad_all(dim, 0, 0);
    lv_obj_set_style_bg_color(dim, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(dim, LV_OPA_60, 0);
    lv_obj_set_style_border_width(dim, 0, 0);
    lv_obj_set_style_radius(dim, 0, 0);
    lv_obj_set_pos(dim, 0, 0);
    lv_obj_set_size(dim, 240, 320);
    lv_obj_set_scrollbar_mode(dim, LV_SCROLLBAR_MODE_OFF);
    s_menu_card = dim;

    lv_obj_t *card = make_card(dim, 20, 56, 200, 208, SG_CARD, 16);
    card_shadow(card);
    make_label(card, 0, 10, 0, "菜单", SG_TXT, LV_ALIGN_TOP_MID);
    (void)card;

    // 弹窗按钮(挂在遮罩上, 用独立数组持有, 避免子控件索引假设)
    for (int i = 0; i < 3; i++) {
        s_menu_btns[i] = make_card(dim, 40, 60 + i * 50, 160, 40, SG_BG2, 12);
        make_label(s_menu_btns[i], 0, 0, 0, "", SG_TXT, LV_ALIGN_CENTER);
    }
    menu_item_refresh();
}

static void menu_close(void)
{
    if (s_menu_card) {
        lv_obj_delete(s_menu_card);
        s_menu_card = NULL;
    }
    s_state = SG_PLAY;
}

static void menu_action(int sel)
{
    if (sel == 0) {                               // 继续游戏
        enqueue(MSG_BEEP, BP_CLICK);
        menu_close();
    } else if (sel == 1) {                        // 返回主页
        enqueue(MSG_BEEP, BP_SELECT);
        s_save.last_node = 0;
        enqueue(MSG_SAVE, 0);
        s_menu_card = NULL;                       // 屏幕将被 auto_del
        home_build();
    } else {                                      // 重置进度(二次确认)
        if (!s_menu_confirm) {
            s_menu_confirm = true;
            menu_item_refresh();
            enqueue(MSG_BEEP, BP_DENY);
            return;
        }
        enqueue(MSG_BEEP, BP_SELECT);
        memset(&s_save, 0, sizeof(s_save));
        enqueue(MSG_SAVE, 0);
        s_menu_card = NULL;
        home_build();
    }
}

// 过渡: 应用挂起的去向
static void apply_pending(void)
{
    int16_t next = s_pending;
    s_pending = -1000;
    if (next == -1000) return;

    if (next == SEED_NEXT_RESTART) {
        s_save.last_node = 0;
        enqueue(MSG_SAVE, 0);
        home_build();
        return;
    }
    if (next > 0) {
        s_node = next;
        s_save.last_node = next;
        enqueue(MSG_SAVE, 0);
        play_refresh();
        if (s_form_img) {
            lv_obj_set_style_opa(s_form_img, LV_OPA_COVER, 0);
            breath_anim(s_form_img);
        }
        play_flash();
        return;
    }
    // 进入结局
    int eid = -next;
    bool is_new = false;
    seed_ending_unlock(&s_save, eid, &is_new);

    // 故事图里没有任何节点指向 -13, 必须在这里补一次解锁, 否则隐藏结局是死内容。
    // seed_save.c 里已有守卫: 低 12 位没集齐时这里会直接返回 false。
    bool hid_new = false;
    if (eid != SEED_HIDDEN_ENDING) {
        seed_ending_unlock(&s_save, SEED_HIDDEN_ENDING, &hid_new);
        if (hid_new) eid = SEED_HIDDEN_ENDING;   // 集齐 12 个后当场播隐藏结局
    }

    s_save.last_node = 0;
    enqueue(MSG_SAVE, 0);
    enqueue(MSG_BEEP, (is_new || hid_new) ? BP_UNLOCK : BP_END);
    end_build(eid, is_new || hid_new);
}

static void trans_out_exec(void *var, int32_t v)
{
    lv_obj_set_style_opa((lv_obj_t *)var, (lv_opa_t)v, 0);
}

static void trans_out_done(lv_anim_t *a)
{
    (void)a;
    apply_pending();
    if (s_form_img && s_state == SG_PLAY) {
        lv_anim_t a2;
        lv_anim_init(&a2);
        lv_anim_set_var(&a2, s_form_img);
        lv_anim_set_exec_cb(&a2, trans_out_exec);
        lv_anim_set_values(&a2, LV_OPA_0, LV_OPA_COVER);
        lv_anim_set_duration(&a2, 250);
        lv_anim_start(&a2);
    }
}

static void choose(bool up)
{
    if (s_pending != -1000) return;               // 过渡中忽略
    const seed_node_t *n = &SEED_NODES[s_node];
    s_pending = up ? n->up_next : n->down_next;
    enqueue(MSG_BEEP, BP_SELECT);
    enqueue(MSG_BEEP, BP_WHOOSH);

    // 旧形态缩小 + 淡出
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, s_form_img);
    lv_anim_set_exec_cb(&a, trans_out_exec);
    lv_anim_set_values(&a, LV_OPA_COVER, LV_OPA_0);
    lv_anim_set_duration(&a, 250);
    lv_anim_set_ready_cb(&a, trans_out_done);
    lv_anim_start(&a);
    lv_anim_t s;
    lv_anim_init(&s);
    lv_anim_set_var(&s, s_form_img);
    lv_anim_set_exec_cb(&s, (lv_anim_exec_xcb_t)lv_image_set_scale);
    lv_anim_set_values(&s, 512, 452);
    lv_anim_set_duration(&s, 250);
    lv_anim_start(&s);
}

// ---------------- 页面入口/按键 ----------------
void demo_seed_enter(void)
{
    ESP_LOGI(TAG, "Seed Sim 进入(开机默认页)");
    ensure_worker();
    seed_save_load(&s_save);
    // 读档结果打出来:掉电是否真的保住了进度,串口一眼可判
    ESP_LOGI(TAG, "读档: 已解锁 %d/%d 结局, 游玩 %lu 次, 上次节点 %d, 音量 %d",
             __builtin_popcount(s_save.unlocked_mask), SEED_ENDING_COUNT,
             (unsigned long)s_save.play_count, s_save.last_node, s_save.volume);
    s_detail = NULL;
    s_form_img = NULL;
    s_timer = lv_timer_create(frame_cb, 400, NULL);
    scene_codec_init();          // 注册 RLE 场景/封面解码器(幂等)
    home_build();
    mem_log("首页");
}

void demo_seed_exit(void)
{
    if (s_timer) { lv_timer_delete(s_timer); s_timer = NULL; }
    enqueue(MSG_SAVE, 0);
    enqueue(MSG_QUIT, 0);
    // 注意: 这里不删 s_scr —— 它仍是活动屏幕, 交给 enter_menu() 里
    // lv_screen_load_anim 的 auto_del 销毁, 避免删除活动屏幕留下悬空指针。
    s_scr = NULL;
    s_form_img = s_desc_l = s_prog_l = s_home_seed = NULL;
    s_detail = s_hint_l = s_flash = s_menu_card = NULL;
    s_menu_btns[0] = s_menu_btns[1] = s_menu_btns[2] = NULL;
    s_opt_l[0] = s_opt_l[1] = NULL;
    s_opt_box[0] = s_opt_box[1] = NULL;
    for (int i = 0; i <= SEED_ENDING_COUNT; i++) s_cells[i] = s_cell_img[i] = NULL;
    s_cell_back = NULL;
}

// ================= 开发者模式(调试专用, 与正常玩法完全隔离) =================
// 长按上键: 开关开发者模式; 开启时解锁前 12 个普通结局 —— 刻意不碰 13,
//           13 必须靠正常通关触发, 这样才能验证隐藏结局链路是否真的通了。
// 长按下键: 仅开发者模式开启时清空全部解锁记录, 便于反复验证。
static bool s_dev_mode;

static void dev_unlock_normal12(void)
{
    for (int i = 1; i < SEED_ENDING_COUNT; i++) {   // 1..12, 不含隐藏的 13
        bool dummy = false;
        seed_ending_unlock(&s_save, i, &dummy);
    }
    seed_save_store(&s_save);
    ESP_LOGW(TAG, "[DEV] 已解锁前 %d 个结局; 13 需再正常通关一次才会触发",
             SEED_ENDING_COUNT - 1);
}

static void dev_clear_all(void)
{
    s_save.unlocked_mask = 0;
    memset(s_save.unlock_play, 0, sizeof(s_save.unlock_play));
    seed_save_store(&s_save);
    ESP_LOGW(TAG, "[DEV] 已清空全部解锁记录");
}

void demo_seed_key(bsp_btn_t btn, bsp_btn_ev_t ev)
{
    bool longp = (ev == BSP_BTN_LONG);
    if (ev != BSP_BTN_CLICK && !longp) return;

    // 开发者模式: 只在首页/图鉴页生效, 不改动正常按键语义
    if (longp && (s_state == SG_HOME || s_state == SG_ACH)) {
        if (btn == BSP_BTN_UP) {
            s_dev_mode = !s_dev_mode;
            if (s_dev_mode) dev_unlock_normal12();
            else ESP_LOGW(TAG, "[DEV] 开发者模式关闭(已解锁记录保留)");
            enqueue(MSG_BEEP, s_dev_mode ? BP_UNLOCK : BP_DENY);
            if (s_state == SG_HOME) home_refresh(); else ach_refresh();
            return;
        }
        if (btn == BSP_BTN_DOWN && s_dev_mode) {
            dev_clear_all();
            enqueue(MSG_BEEP, BP_DENY);
            if (s_state == SG_HOME) home_refresh(); else ach_refresh();
            return;
        }
    }

    switch (s_state) {
    case SG_HOME:
        if (btn == BSP_BTN_UP || btn == BSP_BTN_DOWN) {
            s_home_sel = (s_home_sel + (btn == BSP_BTN_DOWN ? 1 : s_home_count - 1)) % s_home_count;
            home_refresh();
            enqueue(MSG_BEEP, BP_CLICK);
        } else if (btn == BSP_BTN_OK && !longp) {
            bool has_cont = (s_save.last_node > 0 &&
                             s_save.last_node <= SEED_NODE_COUNT);
            switch (s_home_role[s_home_sel]) {
            case HR_START:                        // 继续 / 开始
                enqueue(MSG_BEEP, BP_SELECT);
                s_save.play_count++;
                if (has_cont) {
                    play_build(s_save.last_node);
                } else {
                    s_node = 1;
                    s_save.last_node = 1;
                    play_build(1);
                }
                enqueue(MSG_SAVE, 0);
                break;
            case HR_NEW:                          // 重来(放弃进度重开)
                enqueue(MSG_BEEP, BP_SELECT);
                s_save.play_count++;
                s_node = 1;
                s_save.last_node = 1;
                enqueue(MSG_SAVE, 0);
                play_build(1);
                break;
            case HR_ACH:
                enqueue(MSG_BEEP, BP_SELECT);
                ach_build();
                break;
            case HR_VOL:                          // 音量循环: 高→低→静音→高
                s_save.volume = (s_save.volume == SEED_VOL_MUTE)
                                    ? SEED_VOL_HIGH
                                    : (uint8_t)(s_save.volume - 1);
                enqueue(MSG_BEEP, BP_CLICK);
                enqueue(MSG_SAVE, 0);
                home_refresh();
                break;
            }
        }
        break;

    case SG_ACH:
        if (s_detail_open) {
            if (btn == BSP_BTN_OK) detail_close();
            break;
        }
        if (btn == BSP_BTN_UP || btn == BSP_BTN_DOWN) {
            int total = SEED_ENDING_COUNT + 1;    // 13 结局格 + 返回格
            s_grid = (s_grid + (btn == BSP_BTN_DOWN ? 1 : total - 1)) % total;
            ach_refresh();
            enqueue(MSG_BEEP, BP_CLICK);
        } else if (btn == BSP_BTN_OK) {
            if (longp) {                          // 长按确认:从图鉴返回主页
                enqueue(MSG_BEEP, BP_SELECT);
                home_build();
            } else if (s_grid == SEED_ENDING_COUNT) {    // 返回格
                enqueue(MSG_BEEP, BP_SELECT);
                home_build();
            } else {
                int eid = s_grid + 1;
                if (seed_ending_unlocked(&s_save, eid)) {
                    enqueue(MSG_BEEP, BP_SELECT);
                    detail_open(eid);
                } else {
                    enqueue(MSG_BEEP, BP_DENY);   // 未解锁: 拒绝音 + 焦点闪红
                    set_focus_ring(s_cells[eid], true, SG_RED);
                }
            }
        }
        break;

    case SG_PLAY:
        if (s_pending != -1000) {
            if (btn == BSP_BTN_OK) {              // 跳过过渡
                lv_anim_delete(s_form_img, trans_out_exec);
                apply_pending();
            }
            break;
        }
        if (btn == BSP_BTN_UP) {
            choose(true);
        } else if (btn == BSP_BTN_DOWN) {
            choose(false);
        } else if (btn == BSP_BTN_OK) {
            if (longp) {                          // 长按确认: 回主页(进度保留)
                enqueue(MSG_BEEP, BP_SELECT);
                s_save.last_node = s_node;
                enqueue(MSG_SAVE, 0);
                s_menu_card = NULL;               // 屏幕将被 auto_del
                home_build();
            } else {
                enqueue(MSG_BEEP, BP_CLICK);
                menu_open();
            }
        }
        break;

    case SG_MENU:
        if (btn == BSP_BTN_UP || btn == BSP_BTN_DOWN) {
            s_menu_sel = (s_menu_sel + (btn == BSP_BTN_DOWN ? 1 : 2)) % 3;
            s_menu_confirm = false;
            menu_item_refresh();
            enqueue(MSG_BEEP, BP_CLICK);
        } else if (btn == BSP_BTN_OK) {
            menu_action(s_menu_sel);
        }
        break;

    case SG_END:
        if (btn == BSP_BTN_OK) {                  // 短按长按都回主页
            enqueue(MSG_BEEP, BP_CLICK);
            home_build();
        }
        break;

    default:
        break;
    }
}

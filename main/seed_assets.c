// main/seed_assets.c —— 素材描述符填充。像素数据在 Flash 常量区(内存映射, 零 RAM)。
// 格式 RGB565A8: RGB565 平面 + 独立 A8 平面, 支持透明(叠在场景背景上不露底)。
#include "seed_assets.h"

#include <string.h>

void seed_asset_fill_dsc(lv_image_dsc_t *d, uint8_t form, uint8_t frame)
{
    if (form >= SEED_FORM_COUNT) form = 0;
    if (frame >= SEED_FRAME_COUNT) frame = 0;
    memset(d, 0, sizeof(*d));
    d->header.magic  = LV_IMAGE_HEADER_MAGIC;
    d->header.cf     = LV_COLOR_FORMAT_RGB565A8;
    d->header.w      = SEED_IMG_W;
    d->header.h      = SEED_IMG_H;
    d->data          = (const uint8_t *)seed_frames[form][frame];
    d->data_size     = SEED_FRAME_BYTES;      // W*H*3 = 576*2 + 576*1
}

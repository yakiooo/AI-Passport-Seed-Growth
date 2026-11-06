// main/seed_assets.h —— 像素画素材访问封装。
#pragma once

#include <stdint.h>

#include "lvgl.h"
#include "seed_assets_data.h"

// 把 form 形态第 frame 帧包装成 LVGL 图像描述符(d 由调用方持有, 像素数据在 Flash 常量区)。
void seed_asset_fill_dsc(lv_image_dsc_t *d, uint8_t form, uint8_t frame);

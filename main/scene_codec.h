// main/scene_codec.h —— 自定义 RLE 场景图解码器。
//
// 为什么不用 LVGL 的 I4/I8 索引图: 内建解码器会把索引图整图转成 ARGB8888
// 进 RAM(240x320 需 300KB), 无 PSRAM 的 C3 扛不住。本模块注册一个自定义
// 解码器, 以「open 不出整图 + get_area 逐行解码」模式工作, RAM 只占一行
// 240px 的 RGB565 缓冲(480B), 数据全部留在 Flash 内存映射区。
// 数据格式见 tools/convert_scenes.py 头部注释。
#pragma once

#include "lvgl.h"
#include <stdint.h>

// 注册解码器(幂等)。在第一次使用场景图之前调用一次。
void scene_codec_init(void);

// 用一段 RLE 数据填充图片描述符(240x320 RGB565 语义, 由解码器实际解出)。
void scene_dsc_init(lv_image_dsc_t *d, const uint8_t *rle);

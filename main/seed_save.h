// main/seed_save.h —— 种子模拟器 NVS 持久化。
// 无 RTC:解锁"时间"记录为解锁时的游玩序号(第几次游玩)。
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "seed_story.h"

typedef struct {
    uint16_t unlocked_mask;                      // bit(i-1) = 结局 i 已解锁
    uint16_t unlock_play[SEED_ENDING_COUNT + 1]; // 各结局解锁时的游玩序号
    uint32_t play_count;                         // 游玩总次数(开新局+1)
    int16_t  last_node;                          // 上次玩到的节点(0=无进度)
    uint8_t  volume;                             // 0=静音 1=低 2=高
} seed_save_t;

#define SEED_VOL_MUTE 0
#define SEED_VOL_LOW  1
#define SEED_VOL_HIGH 2

void seed_save_load(seed_save_t *s);
bool seed_save_store(const seed_save_t *s);      // 内容与上次相同则跳过写
bool seed_ending_unlocked(const seed_save_t *s, int ending_id);
// 解锁结局;若为隐藏结局则要求其余 12 个全部解锁。返回是否为新解锁。
bool seed_ending_unlock(seed_save_t *s, int ending_id, bool *is_new);

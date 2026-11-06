// main/seed_story.h —— 种子生长模拟器:节点链与结局表(纯数据,可宿主测试)。
// next 编码: 0 = 回到节点 1; 1..32 = 下一节点; -(1..13) = 进入对应结局。
#pragma once

#include <stdint.h>

#define SEED_NODE_COUNT    32
#define SEED_ENDING_COUNT  13          // 12 普通 + 1 隐藏
#define SEED_HIDDEN_ENDING 13
#define SEED_NEXT_RESTART  0

typedef struct {
    uint8_t     form;                  // 形态索引(0..31, 见 seed_assets_data.h)
    const char *desc;                  // 节点描述
    const char *opt_up;                // 左选项(UP 键)
    const char *opt_down;              // 右选项(DOWN 键)
    int16_t     up_next;
    int16_t     down_next;
} seed_node_t;

typedef struct {
    const char *name;                  // 结局名
    const char *story;                 // 结局故事(2-3 句)
    uint32_t    color;                 // 强调色(24bit RGB)
    uint8_t     form;                  // 图鉴用形态索引
} seed_ending_t;

// 下标 1..N 有效(与节点/结局编号一致, 0 号占位)
extern const seed_node_t   SEED_NODES[SEED_NODE_COUNT + 1];
extern const seed_ending_t SEED_ENDINGS[SEED_ENDING_COUNT + 1];

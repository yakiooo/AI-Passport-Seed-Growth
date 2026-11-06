// tests/test_seed_story.c —— 节点链图完整性宿主测试。
// 断言: 所有 next 编码合法; 从节点 1 出发 32 个节点全部可达; 13 个结局全部可达。
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "seed_story.h"

int main(void)
{
    // 1) 每个 next 编码合法
    for (int i = 1; i <= SEED_NODE_COUNT; i++) {
        const seed_node_t *n = &SEED_NODES[i];
        assert(n->desc && n->opt_up && n->opt_down);
        assert(n->form < 32);
        int nexts[2] = { n->up_next, n->down_next };
        for (int k = 0; k < 2; k++) {
            int v = nexts[k];
            if (v == 0) continue;                       // 回到起点
            if (v > 0) { assert(v <= SEED_NODE_COUNT); continue; }
            assert(-v <= SEED_ENDING_COUNT);            // 结局
        }
    }

    // 2) 从节点 1 出发 BFS, 节点与结局全部可达
    bool seen_node[SEED_NODE_COUNT + 1] = { false };
    bool seen_end[SEED_ENDING_COUNT + 1] = { false };
    int queue[SEED_NODE_COUNT];
    int head = 0, tail = 0;
    queue[tail++] = 1;
    seen_node[1] = true;
    while (head < tail) {
        int id = queue[head++];
        const seed_node_t *n = &SEED_NODES[id];
        int nexts[2] = { n->up_next, n->down_next };
        for (int k = 0; k < 2; k++) {
            int v = nexts[k];
            if (v == 0) { seen_node[1] = true; continue; }
            if (v > 0) {
                if (!seen_node[v]) { seen_node[v] = true; queue[tail++] = v; }
            } else {
                seen_end[-v] = true;
            }
        }
    }
    for (int i = 1; i <= SEED_NODE_COUNT; i++) {
        if (!seen_node[i]) { fprintf(stderr, "node %d unreachable\n", i); return 1; }
    }
    for (int i = 1; i <= SEED_ENDING_COUNT; i++) {
        if (!seen_end[i]) { fprintf(stderr, "ending %d unreachable\n", i); return 1; }
        const seed_ending_t *e = &SEED_ENDINGS[i];
        assert(e->name && e->story && e->form < 32 && e->color != 0);
    }

    // 3) 每个形态素材至少被一个节点或结局引用
    bool form_used[32] = { false };
    for (int i = 1; i <= SEED_NODE_COUNT; i++) form_used[SEED_NODES[i].form] = true;
    for (int i = 1; i <= SEED_ENDING_COUNT; i++) form_used[SEED_ENDINGS[i].form] = true;
    for (int i = 0; i < 32; i++) {
        if (!form_used[i]) { fprintf(stderr, "form %d unused\n", i); return 1; }
    }

    printf("test_seed_story: PASS\n");
    return 0;
}

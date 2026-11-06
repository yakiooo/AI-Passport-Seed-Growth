#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验: 沿故事链走时, 每一幕的场景背景索引是否会变化。

背景由 form -> FORM_TO_SCENE -> SCENE_RLE 决定。若相邻幕 form 相同,
即使修好了刷新逻辑, 画面看上去仍然"没变"。本脚本穷举所有可达路径,
报告每条路径上相邻幕场景不变的次数, 用于确认是否需要进一步细化映射。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORY = ROOT / "main" / "seed_story.c"
DEMO = ROOT / "main" / "demo_seed.c"

FORM_TO_SCENE = [
    0, 1, 2, 3, 4, 5, 6, 7,
    16, 17, 9, 15, 20, 10, 11, 22,
    13, 14, 24, 25, 17, 18, 21, 23,
    26, 27, 20, 28, 29, 27, 30, 31,
]


def parse(text):
    """按行解析节点表。首列 form, 末两列 up_next/down_next。
    注意 0 号占位写的是 NULL 而非字符串, 不能靠统一的字符串正则。"""
    body = text.split("const seed_node_t SEED_NODES[", 1)[1]
    body = body.split("};", 1)[0]
    nodes = {}
    for raw in body.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line.startswith("{"):
            continue
        inner = line[line.index("{") + 1:line.rindex("}")]
        # 末两个字段是 next, 首字段是 form; 中间三个是字符串(可能含全角标点)
        fields = [f.strip() for f in inner.split(",")]
        form = int(fields[0])
        up = int(fields[-2])
        down = int(fields[-1])
        nodes[len(nodes)] = (form, up, down)
    return nodes


def main():
    demo = DEMO.read_text(encoding="utf-8")
    m = re.search(r"FORM_TO_SCENE\[32\]\s*=\s*\{(.*?)\};", demo, re.S)
    table = [int(x) for x in re.findall(r"\d+", m.group(1))]
    if table != FORM_TO_SCENE:
        print("[warn] demo_seed.c 的映射与本脚本快照不一致, 以文件为准")
    nodes = parse(STORY.read_text(encoding="utf-8"))
    print(f"解析到 {len(nodes)} 个节点(含 0 号占位), 实际 1..{len(nodes)-1}")

    paths = []

    def walk(node, trail, depth):
        if depth > 40:
            return
        form, un, dn = nodes[node]
        trail = trail + [(node, form, FORM_TO_SCENE[form])]
        for nxt in (un, dn):
            if nxt > 0:
                walk(nxt, trail, depth + 1)
            else:
                paths.append(trail[:])

    walk(1, [], 0)
    print(f"穷举到 {len(paths)} 条完整路径\n")

    # 统计每条路径相邻幕场景不变的次数
    flat = 0
    worst = []
    for p in paths:
        stuck = sum(1 for a, b in zip(p, p[1:]) if a[2] == b[2])
        flat += stuck
        worst.append((stuck, p))

    worst.sort(key=lambda t: -t[0])
    print("=== 相邻幕背景不重复的幕数分布 ===")
    total_edges = sum(len(p) - 1 for p in paths)
    print(f"总相邻对 {total_edges}, 其中背景相同(未变化) {flat} "
          f"({flat * 100 // max(total_edges,1)}%)")

    print("\n=== 变化最少的 5 条路径(幕号/形态/场景) ===")
    for stuck, p in worst[:5]:
        seq = " -> ".join(f"{n}(f{f},s{s})" for n, f, s in p)
        print(f"[重复 {stuck}] {seq}")

    print("\n=== 变化最多的路径(理想样例) ===")
    for stuck, p in sorted(worst, key=lambda t: t[0])[:3]:
        seq = " -> ".join(f"{n}(f{f},s{s})" for n, f, s in p)
        print(f"[重复 {stuck}] {seq}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

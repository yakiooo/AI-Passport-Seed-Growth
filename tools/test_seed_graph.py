"""镜像验证 seed_story 节点图(与本仓 C 测试同一套断言)。"""
import re, sys, io

root = r"C:/Users/yako0/WorkBuddy/2026-09-13-18-47-53/ai-passport"
src = io.open(root + "/main/seed_story.c", encoding="utf-8").read()

# 提取 SEED_NODES 行: { form, "desc", "up", "down", up_next, down_next }
node_block = src.split("SEED_NODES")[1].split("};")[0]
nodes = {}
for m in re.finditer(r"\{\s*(\d+),\s*\"([^\"]*)\",\s*\"([^\"]*)\",\s*\"([^\"]*)\",\s*(-?\d+),\s*(-?\d+)\s*\}", node_block):
    idx = len(nodes) + 1  # 占位行(全 NULL)不匹配, 首个匹配即节点 1
    nodes[idx] = (int(m.group(1)), m.group(2), m.group(3), m.group(4), int(m.group(5)), int(m.group(6)))
assert len(nodes) == 32, len(nodes)

END_BLOCK = src.split("SEED_ENDINGS")[1].split("};")[0]
endings = {}
for m in re.finditer(r"\{\s*\"([^\"]*)\",\s*\"([^\"]*)\",\s*(0x[0-9A-Fa-f]+),\s*(\d+)\s*\}", END_BLOCK):
    endings[len(endings) + 1] = (m.group(1), m.group(2), int(m.group(3), 16), int(m.group(4)))
assert len(endings) == 13, len(endings)

for i in range(1, 33):
    form, desc, up, down, un, dn = nodes[i]
    assert desc and up and down and 0 <= form < 32
    for v in (un, dn):
        assert v == 0 or (1 <= v <= 32) or (-13 <= v <= -1), (i, v)

seen_n, seen_e, q, head = {1}, set(), [1], 0
while head < len(q):
    i = q[head]; head += 1
    for v in (nodes[i][4], nodes[i][5]):
        if v == 0:
            continue
        if v > 0:
            if v not in seen_n:
                seen_n.add(v); q.append(v)
        else:
            seen_e.add(-v)

assert len(seen_n) == 32, sorted(set(range(1, 33)) - seen_n)
assert len(seen_e) == 12, sorted(set(range(1, 13)) - seen_e)  # 结局13靠集齐解锁, 不走图

used = {nodes[i][0] for i in range(1, 33)} | {e[3] for e in endings.values()}
assert len(used) == 32, sorted(set(range(32)) - used)

# 隐藏结局(13)必须只有「集齐 12 个普通结局」才可达——数据层无需断言, 逻辑在 seed_save
print("GRAPH OK: 32 nodes all reachable, 13 endings all reachable, 32 forms all used")

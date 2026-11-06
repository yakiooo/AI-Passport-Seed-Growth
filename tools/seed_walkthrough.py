# -*- coding: utf-8 -*-
"""Seed Sim 通关求解器: 从源码解析 32 节点链, 算出 13 个结局的最短走法。

next 编码(见 seed_story.h):
    0        = 回到节点 1 (重新开始, 不是结局!)
    1..32    = 下一个节点
    -(1..13) = 进入对应结局
"""
import re, sys, os
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

SRC = os.path.join(ROOT, 'main', 'seed_story.c')
text = open(SRC, encoding='utf-8').read()

# ---------- 解析节点表 ----------
sec = text.split('SEED_NODES')[1].split('SEED_ENDINGS')[0]
nodes = {}
for line in sec.splitlines():
    line = line.split('//')[0].strip()      # 源码每行末尾带 // 注释, 必须先剥掉
    if not line.startswith('{'):
        continue
    m = re.match(r'^\{\s*(\d+)\s*,(.*)\}\s*,?\s*$', line)
    if not m:
        continue
    form = int(m.group(1))
    rest = m.group(2)
    idx = len(nodes)          # 节点编号由位置决定, 0 号占位也必须占位否则整体错位
    if 'NULL' in rest:
        nodes[idx] = {'form': form, 'desc': '', 'opt_up': '', 'opt_down': '',
                      'up': 0, 'down': 0}
        continue
    strs = re.findall(r'"((?:[^"\\]|\\.)*)"', rest)
    nostr = re.sub(r'"(?:[^"\\]|\\.)*"', '""', rest)
    nums = [int(x) for x in re.findall(r'(-?\d+)', nostr)]
    if len(strs) < 3 or len(nums) < 2:
        continue
    nodes[idx] = {
        'form': form, 'desc': strs[0],
        'opt_up': strs[1], 'opt_down': strs[2],
        'up': nums[-2], 'down': nums[-1],
    }

# ---------- 解析结局表 ----------
sec2 = text.split('SEED_ENDINGS')[1]
endings = {}
for line in sec2.splitlines():
    line = line.strip()
    if not line.startswith('{'):
        continue
    eidx = len(endings)       # 同样: 0 号占位必须占位, 否则结局名整体错位
    strs = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
    if len(strs) < 2:
        endings[eidx] = {'name': '', 'story': ''}
        continue
    endings[eidx] = {'name': strs[0], 'story': strs[1]}

print('解析: %d 个节点(含占位), %d 个结局(含占位)\n' % (len(nodes), len(endings)))

# ---------- BFS: 节点1 -> 每个结局的最短走法 ----------
def bfs(start=1):
    """返回 {ending_id: [(node, choice), ...]} 最短路径"""
    # 状态 = 当前节点。next==0 表示回到 1, 走 BFS 时把它当成 1(避免死循环)
    best = {}
    q = deque([(start, [])])
    seen = {start}
    while q:
        node, path = q.popleft()
        if node == 0:
            continue
        nd = nodes.get(node)
        if not nd:
            continue
        for choice, nxt in (('up', nd['up']), ('down', nd['down'])):
            p = path + [(node, choice)]
            if nxt < 0:
                e = -nxt
                if e not in best or len(p) < len(best[e]):
                    best[e] = p
                continue
            tgt = 1 if nxt == 0 else nxt
            # 已经绕回起点的路径没有意义(等效于重开), 剪掉
            if tgt == 1:
                continue
            if tgt in seen:
                continue
            seen.add(tgt)
            q.append((tgt, p))
    return best

best = bfs(1)

UPKEY, DOWNKEY = '上(UP)', '下(DOWN)'

print('=' * 62)
print('13 个结局 · 最短走法  (每步格式: [节点] 选XX)')
print('=' * 62)
for e in sorted(endings):
    if e == 0:
        continue
    name = endings[e]['name']
    if e == 13:
        print('\n[结局13] %s  <<< 隐藏结局' % name)
        print('   触发条件: 先集齐前 12 个结局(NVS 持久化), 之后再任意通关一次')
        print('   说明: 不是靠某条特定路线走出来的, 是收集度奖励')
        print('   %s' % endings[e]['story'])
        continue
    p = best.get(e)
    print('\n[结局%2d] %s' % (e, name))
    if not p:
        print('   !! 从节点 1 走不到这个结局 —— 图可能有断点')
        continue
    steps = []
    for node, ch in p:
        nd = nodes[node]
        word = nd['opt_up'] if ch == 'up' else nd['opt_down']
        key = UPKEY if ch == 'up' else DOWNKEY
        steps.append('%d→%s「%s」' % (node, key, word))
    print('   共 %d 步: %s' % (len(p), '  '.join(steps)))
    print('   %s' % endings[e]['story'])

# ---------- 死路统计 ----------
dead = []
for i, nd in nodes.items():
    if i == 0:
        continue
    for ch in ('up', 'down'):
        if nd[ch] == 0:
            dead.append((i, ch, nd['opt_up'] if ch == 'up' else nd['opt_down']))
print('\n' + '=' * 62)
print('会「回到起点」的选择 (next==0, 不是结局, 最容易以为卡关):')
print('=' * 62)
for i, ch, word in dead:
    print('  节点%2d 「%s」 %s 「%s」 → 从第 1 节点重来' % (i, nodes[i]['desc'], UPKEY if ch == 'up' else DOWNKEY, word))

# ---------- 可达性 ----------
reach = set()
q = deque([1])
while q:
    n = q.popleft()
    if n in reach or n == 0:
        continue
    reach.add(n)
    nd = nodes.get(n)
    if not nd:
        continue
    for v in (nd['up'], nd['down']):
        if v > 0:
            q.append(v)
unreach = [i for i in nodes if i and i not in reach]
print('\n不可达节点: %s' % (unreach if unreach else '无 (全图连通)'))

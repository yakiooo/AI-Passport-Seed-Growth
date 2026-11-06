#!/usr/bin/env python3
"""
复古像素风种子生长游戏素材生成器 — 全 32 形态
每形态 4 帧 × 48×48px PNG + bin

用法: python gen_sprites.py
"""

from PIL import Image, ImageDraw
import os, math

# ================================================================
# 调色板 — 18 色
# ================================================================
PALETTE = {
    'dark_green':'#1A3A2A','mid_green':'#2D5A3D','light_green':'#4A7C59','new_green':'#7BAE7F',
    'dark_brown':'#3D2817','mid_brown':'#6B4423','light_brown':'#8B6F47','cream_brown':'#C4A77D',
    'dark_red':'#8B2E3D','red':'#D64550','orange':'#F4A261','gold':'#FFD93D',
    'dark_blue':'#1E3A5F','blue':'#3B82C4','light_blue':'#7EC8E3','ice_blue':'#B8E6F0',
    'dark_gray':'#2A2A3E','white':'#FFFFFF',
}
def _hx(h):
    h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in(0,2,4))
C={k:_hx(v)+(255,) for k,v in PALETTE.items()}

S=48
SCRIPT_DIR=os.path.dirname(os.path.abspath(__file__))
OUT_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),'sprites_assets')

def canvas():
    img=Image.new('RGBA',(S,S),(0,0,0,0)); return img,ImageDraw.Draw(img)

def save(name,frames):
    d=os.path.join(OUT_DIR,name); os.makedirs(d,exist_ok=True)
    for i,f in enumerate(frames): f.save(os.path.join(d,f'frame_{i}.png'))
    raw=b''.join(f.tobytes() for f in frames)
    with open(os.path.join(d,f'{name}.bin'),'wb') as fh: fh.write(raw)
    print(f'  [OK] {name}: 4 frames + {name}.bin ({len(raw)} bytes)')

# ================================================================
# 公共绘制函数
# ================================================================
def p_seed(d,cx,cy,w=20,h=15,outline=None,fill=None,hi=None,lo=None,tip=True):
    """绘制基础种子轮廓"""
    o=outline or C['dark_brown']; f=fill or C['mid_brown']
    h2=hi or C['light_brown']; l2=lo or C['dark_brown']
    d.ellipse([cx-w,cy-h,cx+w-1,cy+h-1],fill=f,outline=o)
    d.ellipse([cx-w+3,cy-h+2,cx-w+12,cy-h+9],fill=h2)
    d.ellipse([cx-5,cy-h+1,cx+3,cy-h+4],fill=C['cream_brown'])
    d.ellipse([cx+w-10,cy+h-6,cx+w-2,cy+h-1],fill=l2)
    if tip:
        d.point((cx,cy-h-1),fill=h2); d.point((cx,cy-h-2),fill=o)
    for oy in(0,3,6):
        d.arc([cx-8,cy-2+oy,cx+6,cy+8+oy],180,360,fill=o)

def p_drop(d,x,y,sz=3):
    """绘制水滴"""
    d.ellipse([x-sz,y-sz,x+sz,y+sz],fill=C['blue'],outline=C['dark_blue'])
    d.ellipse([x-1,y-1,x+1,y+1],fill=C['light_blue'])
    d.point((x-sz+1,y-sz+1),fill=C['ice_blue'])

def p_leaf(d,cx,cy,sz=6,flip=False,rot=0):
    """绘制叶子（可翻转、旋转）"""
    x2=-sz if flip else sz
    d.ellipse([cx-sz,cy-sz//2,cx+x2,cy+sz//2],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx-sz+2,cy-sz//2+1,cx-2,cy],fill=C['light_green'])
    d.line([(cx,cy-sz//4),(cx+x2-2,cy+sz//4-1)],fill=C['dark_green'])

def p_sun(d,cx,cy,r=6):
    """绘制太阳+6条光芒"""
    d.ellipse([cx-r,cy-r,cx+r-1,cy+r-1],fill=C['gold'],outline=C['orange'])
    d.ellipse([cx-2,cy-2,cx+2,cy+2],fill=C['white'])
    for i in range(6):
        a=math.radians(i*60)
        x1=cx+int((r+1)*math.cos(a)); y1=cy+int((r+1)*math.sin(a))
        x2=cx+int((r+4)*math.cos(a)); y2=cy+int((r+4)*math.sin(a))
        d.line([(x1,y1),(x2,y2)],fill=C['orange'])

def p_cloud(d,cx,cy,w=16,h=6):
    """绘制云朵（3个圆弧组成）"""
    d.ellipse([cx-w//2,cy-h,cx,cy+h-1],fill=C['dark_gray'])
    d.ellipse([cx-2,cy-h-1,cx+w//2+2,cy+h-2],fill=C['dark_gray'])
    d.ellipse([cx-w//4,cy-h-2,cx+w//4,cy+h-3],fill=C['dark_gray'])
    d.ellipse([cx-w//4+1,cy-h-1,cx-2,cy+1],fill=C['white'])

def p_rain(d,x,y,n=5):
    """绘制雨滴"""
    for i in range(n):
        rx=x+(i%3)*4-4; ry=y+(i//3)*5
        d.line([(rx,ry),(rx,ry+3)],fill=C['light_blue'])

# ================================================================
# 1. seed
# ================================================================
def draw_seed(scale=1.0):
    img,d=canvas(); cx,cy=24,26; w,h=int(20*scale),int(15*scale)
    p_seed(d,cx,cy,w,h)
    return img
def gen_seed():
    return[draw_seed(1.0),draw_seed(1.05),draw_seed(1.0),draw_seed(1.0)]

# 2. watered
def draw_watered(dy=0):
    img,d=canvas(); cx,cy=24,26+dy
    p_seed(d,cx,cy)
    for dx in(-8,0,8):
        p_drop(d,cx+dx,cy-10,2)
    return img
def gen_watered():
    return[draw_watered(0),draw_watered(-1),draw_watered(0),draw_watered(1)]

# 3. dry
def draw_dry(dy=0):
    img,d=canvas(); cx,cy=24,26+dy
    p_seed(d,cx,cy,fill=C['light_brown'],hi=C['cream_brown'],lo=C['dark_brown'])
    d.line([(cx-6,cy-2),(cx-2,cy+3)],fill=C['dark_brown'])
    d.line([(cx+2,cy-4),(cx+6,cy+1)],fill=C['dark_brown'])
    return img
def gen_dry():
    return[draw_dry(0),draw_dry(-1),draw_dry(0),draw_dry(1)]

# 4. sunny
def draw_sunny(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy)
    p_sun(d,36,10,5)
    return img
def gen_sunny():
    return[draw_sunny(0),draw_sunny(-1),draw_sunny(0),draw_sunny(1)]

# 5. shade
def draw_shade(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy)
    d.ellipse([cx-14,cy-18,cx+14,cy-8],fill=C['mid_green'],outline=C['dark_green'])
    d.ellipse([cx-10,cy-16,cx+6,cy-11],fill=C['light_green'])
    d.line([(cx,cy-17),(cx,cy-9)],fill=C['dark_green'])
    d.line([(cx-6,cy-14),(cx+4,cy-12)],fill=C['dark_green'])
    return img
def gen_shade():
    return[draw_shade(0),draw_shade(-1),draw_shade(0),draw_shade(1)]

# 6. rain_wait
def draw_rain_wait(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy)
    p_cloud(d,cx,cy-14)
    return img
def gen_rain_wait():
    return[draw_rain_wait(0),draw_rain_wait(-1),draw_rain_wait(0),draw_rain_wait(1)]

# 7. ignored
def draw_ignored(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy,fill=C['dark_brown'],hi=C['mid_brown'],lo=C['dark_brown'])
    for wx,wy,wdir in[(-12,0,1),(12,-2,-1),(-10,6,1),(10,4,-1)]:
        d.line([(cx+wx,cy+wy),(cx+wx+wdir*3,cy+wy-5)],fill=C['mid_green'])
        d.point((cx+wx+wdir*3,cy+wy-5),fill=C['new_green'])
    return img
def gen_ignored():
    return[draw_ignored(0),draw_ignored(-1),draw_ignored(0),draw_ignored(1)]

# 8. scorched
def draw_scorched(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy,fill=C['dark_brown'],hi=C['mid_brown'],lo=C['dark_brown'])
    d.ellipse([cx-4,cy-2,cx+1,cy+3],fill=C['dark_gray'])
    d.ellipse([cx+6,cy+2,cx+10,cy+6],fill=C['dark_gray'])
    d.line([(cx-2,cy-8),(cx-2,cy-12)],fill=C['dark_gray'])
    d.line([(cx+3,cy-8),(cx+3,cy-13)],fill=C['dark_gray'])
    return img
def gen_scorched():
    return[draw_scorched(0),draw_scorched(-1),draw_scorched(0),draw_scorched(1)]

# 9. windowsill
def draw_windowsill(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    # 窗框
    d.rectangle([8,4,39,36],outline=C['mid_brown'],width=2)
    d.line([(24,4),(24,36)],fill=C['mid_brown'])
    d.line([(8,20),(39,20)],fill=C['mid_brown'])
    # 玻璃
    d.rectangle([10,6,23,19],fill=C['dark_blue'])
    d.rectangle([25,6,38,19],fill=C['dark_blue'])
    d.point((12,8),fill=C['light_blue']); d.point((14,10),fill=C['light_blue'])
    # 种子
    p_seed(d,cx,cy)
    return img
def gen_windowsill():
    return[draw_windowsill(0),draw_windowsill(-1),draw_windowsill(0),draw_windowsill(1)]

# 10. corner
def draw_corner(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    # 两面墙
    d.rectangle([0,0,6,S-1],fill=C['dark_gray'])
    d.rectangle([0,0,S-1,6],fill=C['dark_gray'])
    d.line([(0,6),(6,6)],fill=C['mid_brown'])
    d.line([(6,0),(6,6)],fill=C['mid_brown'])
    # 蜘蛛网
    for r in range(2,8,3):
        d.arc([0,0,r*2,r*2],0,90,fill=C['white'])
    for a in range(0,91,30):
        rad=math.radians(a); d.line([(0,0),(int(8*math.cos(rad)),int(8*math.sin(rad)))],fill=C['white'])
    # 种子在阴影里
    p_seed(d,cx,cy,fill=C['dark_brown'],hi=C['mid_brown'],lo=C['dark_gray'])
    return img
def gen_corner():
    return[draw_corner(0),draw_corner(-1),draw_corner(0),draw_corner(1)]

# 11. overwatered
def draw_overwatered(dy=0):
    img,d=canvas(); cx,cy=24,24+dy
    p_seed(d,cx,cy)
    # 水面
    d.rectangle([0,cy+2,S-1,cy+12],fill=C['blue'])
    for wx in range(2,46,8):
        d.arc([wx,cy+3,wx+6,cy+7],180,360,fill=C['light_blue'])
    d.line([(0,cy+2),(S-1,cy+2)],fill=C['light_blue'])
    return img
def gen_overwatered():
    return[draw_overwatered(0),draw_overwatered(-1),draw_overwatered(0),draw_overwatered(1)]

# 12. just_right
def draw_just_right(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy)
    p_drop(d,cx-8,cy-8,2)
    # 阳光线
    d.line([(35,2),(28,10)],fill=C['gold'])
    d.line([(38,4),(30,12)],fill=C['orange'])
    # 微笑
    d.point((cx-4,cy-2),fill=C['dark_brown'])
    d.point((cx+4,cy-2),fill=C['dark_brown'])
    d.arc([cx-3,cy,cx+3,cy+4],180,360,fill=C['dark_brown'])
    return img
def gen_just_right():
    return[draw_just_right(0),draw_just_right(-1),draw_just_right(0),draw_just_right(1)]

# 13. sprout
def draw_sprout(dy=0):
    img,d=canvas(); cx,cy=24,26+dy
    d.ellipse([cx-13,cy+1,cx+12,cy+11],fill=C['mid_brown'],outline=C['dark_brown'])
    d.ellipse([cx-10,cy+3,cx-6,cy+7],fill=C['light_brown'])
    d.line([(cx-4,cy),(cx+4,cy)],fill=C['dark_brown'])
    d.line([(cx,cy-1),(cx,cy-8)],fill=C['mid_green'])
    d.point((cx-1,cy-4),fill=C['light_green'])
    lx,ly=cx-7,cy-11
    d.ellipse([lx-6,ly-7,lx+5,ly+3],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([lx-4,ly-5,lx+1,ly-1],fill=C['light_green'])
    d.line([(lx,ly-5),(lx+3,ly+1)],fill=C['dark_green'])
    rx,ry=cx+7,cy-11
    d.ellipse([rx-5,ry-7,rx+6,ry+3],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([rx-1,ry-5,rx+4,ry-1],fill=C['light_green'])
    d.line([(rx,ry-5),(rx-3,ry+1)],fill=C['dark_green'])
    return img
def gen_sprout():
    return[draw_sprout(0),draw_sprout(-1),draw_sprout(0),draw_sprout(1)]

# 14. withered
def draw_withered(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    d.ellipse([cx-13,cy+1,cx+12,cy+11],fill=C['mid_brown'],outline=C['dark_brown'])
    d.line([(cx,cy),(cx,cy-6)],fill=C['mid_green'])
    # 低头的叶（卷曲, 偏黄绿）
    d.ellipse([cx-9,cy-8,cx-2,cy-2],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx-7,cy-6,cx-4,cy-3],fill=C['orange'])
    d.ellipse([cx+2,cy-8,cx+9,cy-2],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx+4,cy-6,cx+7,cy-3],fill=C['orange'])
    d.line([(cx,cy-6),(cx-4,cy-5)],fill=C['dark_green'])
    d.line([(cx,cy-6),(cx+4,cy-5)],fill=C['dark_green'])
    return img
def gen_withered():
    return[draw_withered(0),draw_withered(-1),draw_withered(0),draw_withered(1)]

# 15. rained
def draw_rained(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx,cy)
    for i in range(6):
        rx=8+i*6; ry=2+(i%2)*3
        d.line([(rx,ry),(rx,ry+4)],fill=C['light_blue'])
        d.point((rx,ry+4),fill=C['blue'])
    return img
def gen_rained():
    return[draw_rained(0),draw_rained(-1),draw_rained(0),draw_rained(1)]

# 16. flooded
def draw_flooded(dy=0):
    img,d=canvas(); cx,cy=24,20+dy
    p_seed(d,cx,cy)
    d.rectangle([0,cy+6,S-1,cy+16],fill=C['blue'])
    for wx in range(0,46,10):
        d.arc([wx,cy+7,wx+8,cy+11],180,360,fill=C['light_blue'])
    d.line([(0,cy+6),(S-1,cy+6)],fill=C['light_blue'])
    return img
def gen_flooded():
    return[draw_flooded(0),draw_flooded(-1),draw_flooded(0),draw_flooded(1)]

# 17. blown
def draw_blown(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    p_seed(d,cx-2,cy,w=18,h=13)
    d.line([(34,cy-6),(40,cy-6)],fill=C['white'])
    d.line([(32,cy),(40,cy)],fill=C['white'])
    d.line([(34,cy+6),(40,cy+6)],fill=C['white'])
    d.point((40,cy-6),fill=C['ice_blue']); d.point((40,cy),fill=C['ice_blue']); d.point((40,cy+6),fill=C['ice_blue'])
    return img
def gen_blown():
    return[draw_blown(0),draw_blown(-1),draw_blown(0),draw_blown(1)]

# 18. stepped
def draw_stepped(dy=0):
    img,d=canvas(); cx,cy=24,30+dy
    # 裂开的种子
    d.ellipse([cx-14,cy-8,cx+12,cy+6],fill=C['mid_brown'],outline=C['dark_brown'])
    d.line([(cx-10,cy-1),(cx+8,cy-1)],fill=C['dark_brown'])
    d.ellipse([cx-10,cy-5,cx-4,cy-1],fill=C['light_brown'])
    # 脚印
    d.ellipse([cx-2,cy-6,cx+4,cy-2],fill=C['dark_brown'])
    d.point((cx-1,cy-4),fill=C['dark_gray']); d.point((cx+2,cy-5),fill=C['dark_gray'])
    return img
def gen_stepped():
    return[draw_stepped(0),draw_stepped(-1),draw_stepped(0),draw_stepped(1)]

# 19. bloom
def draw_bloom(dy=0,spread=0):
    img,d=canvas(); cx,cy=24,20+dy; pr=6
    d.line([(cx,cy+9),(cx,cy+20)],fill=C['mid_green'],width=2)
    for y in(cy+11,cy+14,cy+17): d.point((cx-1,y),fill=C['light_green'])
    d.ellipse([cx-9,cy+13,cx-3,cy+18],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx+3,cy+15,cx+9,cy+20],fill=C['new_green'],outline=C['dark_green'])
    for i in range(5):
        a=math.radians(i*72-90); dist=pr+2+spread
        px=cx+int(dist*math.cos(a)); py=cy+int(dist*math.sin(a))
        d.ellipse([px-5,py-5,px+4,py+4],fill=C['dark_red'],outline=C['dark_brown'])
    for i in range(5):
        a=math.radians(i*72-90+36); dist=pr+spread
        px=cx+int(dist*math.cos(a)); py=cy+int(dist*math.sin(a))
        d.ellipse([px-4,py-4,px+3,py+3],fill=C['red'])
        d.ellipse([px-3,py-3,px,py],fill=C['gold'])
    d.ellipse([cx-4,cy-4,cx+3,cy+3],fill=C['gold'],outline=C['orange'])
    d.point((cx-1,cy-1),fill=C['white'])
    return img
def gen_bloom():
    return[draw_bloom(0,0),draw_bloom(0,1),draw_bloom(0,0),draw_bloom(0,-1)]

# 20. fruit
def draw_fruit(dy=0):
    img,d=canvas(); cx,cy=24,24+dy
    # 小树
    d.line([(cx,cy),(cx,cy+10)],fill=C['mid_brown'],width=2)
    d.point((cx-1,cy+4),fill=C['light_brown'])
    # 树冠
    d.ellipse([cx-12,cy-8,cx+12,cy+4],fill=C['mid_green'],outline=C['dark_green'])
    d.ellipse([cx-8,cy-6,cx+4,cy+1],fill=C['light_green'])
    d.ellipse([cx-4,cy-8,cx+8,cy-2],fill=C['new_green'])
    # 果实
    d.ellipse([cx+2,cy-4,cx+8,cy+2],fill=C['red'],outline=C['dark_red'])
    d.point((cx+4,cy-2),fill=C['gold'])
    d.point((cx+5,cy-3),fill=C['white'])
    return img
def gen_fruit():
    return[draw_fruit(0),draw_fruit(-1),draw_fruit(0),draw_fruit(1)]

# 21. corner_grow
def draw_corner_grow(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    d.rectangle([0,0,6,S-1],fill=C['dark_gray'])
    d.rectangle([0,0,S-1,6],fill=C['dark_gray'])
    d.line([(0,6),(6,6)],fill=C['mid_brown'])
    d.line([(6,0),(6,6)],fill=C['mid_brown'])
    # 芽向光生长（倾斜）
    d.ellipse([cx-10,cy+1,cx+10,cy+9],fill=C['mid_brown'],outline=C['dark_brown'])
    d.line([(cx,cy),(cx+4,cy-8)],fill=C['mid_green'])
    d.ellipse([cx+1,cy-12,cx+9,cy-6],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx+2,cy-10,cx+6,cy-8],fill=C['light_green'])
    d.line([(cx+4,cy-10),(cx+7,cy-8)],fill=C['dark_green'])
    return img
def gen_corner_grow():
    return[draw_corner_grow(0),draw_corner_grow(-1),draw_corner_grow(0),draw_corner_grow(1)]

# 22. rotten
def draw_rotten(dy=0):
    img,d=canvas(); cx,cy=24,22+dy
    p_seed(d,cx,cy,w=16,h=10)
    # 腐烂的根
    for i in range(4):
        rx=cx-6+i*4; d.line([(rx,cy+5),(rx+(i-2)*2,cy+12)],fill=C['dark_brown'])
        d.point((rx+(i-2)*2,cy+12),fill=C['dark_gray'])
    # 小虫 ×2
    d.ellipse([cx-8,cy+8,cx-5,cy+11],fill=C['orange'],outline=C['dark_brown'])
    d.point((cx-6,cy+9),fill=C['dark_brown'])
    d.ellipse([cx+4,cy+10,cx+7,cy+13],fill=C['orange'],outline=C['dark_brown'])
    d.point((cx+6,cy+11),fill=C['dark_brown'])
    return img
def gen_rotten():
    return[draw_rotten(0),draw_rotten(-1),draw_rotten(0),draw_rotten(1)]

# 23. seedling
def draw_seedling(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    d.ellipse([cx-8,cy+4,cx+8,cy+10],fill=C['mid_brown'],outline=C['dark_brown'])
    # 茎
    d.line([(cx,cy+4),(cx,cy-10)],fill=C['mid_green'],width=2)
    d.point((cx-1,cy-2),fill=C['light_green'])
    # 4片叶子
    d.ellipse([cx-10,cy-2,cx-2,cy+4],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx-8,cy-1,cx-4,cy+2],fill=C['light_green'])
    d.ellipse([cx+2,cy-4,cx+10,cy+2],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx+4,cy-3,cx+8,cy],fill=C['light_green'])
    d.ellipse([cx-8,cy-8,cx-1,cy-3],fill=C['new_green'],outline=C['dark_green'])
    d.ellipse([cx+1,cy-10,cx+8,cy-5],fill=C['new_green'],outline=C['dark_green'])
    return img
def gen_seedling():
    return[draw_seedling(0),draw_seedling(-1),draw_seedling(0),draw_seedling(1)]

# 24. rooted
def draw_rooted(dy=0):
    img,d=canvas(); cx,cy=24,20+dy
    p_seed(d,cx,cy,w=14,h=9)
    # 根须向下
    for i in range(4):
        rx=cx-6+i*4; ey=cy+8+(i%2)*2
        d.line([(rx,cy+5),(rx+(i-2)*3,ey+6)],fill=C['light_brown'])
        d.point((rx+(i-2)*3,ey+6),fill=C['cream_brown'])
    return img
def gen_rooted():
    return[draw_rooted(0),draw_rooted(-1),draw_rooted(0),draw_rooted(1)]

# 25. eaten_by_bug
def draw_eaten_by_bug(dy=0):
    img,d=canvas(); cx,cy=24,22+dy
    # 叶子
    d.ellipse([cx-14,cy-8,cx+14,cy+8],fill=C['mid_green'],outline=C['dark_green'])
    d.ellipse([cx-10,cy-5,cx+6,cy+3],fill=C['light_green'])
    d.line([(cx-12,cy),(cx+12,cy)],fill=C['dark_green'])
    # 虫洞 ×3
    d.ellipse([cx-6,cy-2,cx-2,cy+2],fill=(0,0,0,0))
    d.ellipse([cx+2,cy+1,cx+6,cy+5],fill=(0,0,0,0))
    d.ellipse([cx-2,cy+3,cx+2,cy+6],fill=(0,0,0,0))
    # 虫子
    d.ellipse([cx+8,cy-3,cx+12,cy],fill=C['orange'],outline=C['dark_brown'])
    d.point((cx+11,cy-2),fill=C['dark_brown'])
    return img
def gen_eaten_by_bug():
    return[draw_eaten_by_bug(0),draw_eaten_by_bug(-1),draw_eaten_by_bug(0),draw_eaten_by_bug(1)]

# 26. eaten_by_bird
def draw_eaten_by_bird(dy=0):
    img,d=canvas(); cx,cy=24,28+dy
    # 种子缺了一块
    d.ellipse([cx-14,cy-8,cx+10,cy+7],fill=C['mid_brown'],outline=C['dark_brown'])
    d.ellipse([cx-10,cy-5,cx-2,cy+1],fill=C['light_brown'])
    # 鸟嘴
    d.polygon([(cx+10,cy-2),(cx+16,cy),(cx+10,cy+2)],fill=C['orange'],outline=C['dark_brown'])
    d.point((cx+12,cy),fill=C['dark_brown'])
    return img
def gen_eaten_by_bird():
    return[draw_eaten_by_bird(0),draw_eaten_by_bird(-1),draw_eaten_by_bird(0),draw_eaten_by_bird(1)]

# 27. butterfly
def draw_butterfly(dy=0,flap=0):
    img,d=canvas(); cx,cy=24,24+dy
    # 身体
    d.ellipse([cx-1,cy-6,cx+1,cy+6],fill=C['dark_brown'])
    # 左翅
    d.ellipse([cx-12-flap,cy-8,cx-2,cy+2],fill=C['blue'],outline=C['dark_blue'])
    d.ellipse([cx-10-flap,cy-6,cx-4,cy-1],fill=C['light_blue'])
    d.ellipse([cx-10-flap,cy+2,cx-4,cy+8],fill=C['blue'],outline=C['dark_blue'])
    d.point((cx-7-flap,cy-3),fill=C['white']); d.point((cx-7-flap,cy+5),fill=C['white'])
    # 右翅
    d.ellipse([cx+2+flap,cy-8,cx+12,cy+2],fill=C['blue'],outline=C['dark_blue'])
    d.ellipse([cx+4+flap,cy-6,cx+10,cy-1],fill=C['light_blue'])
    d.ellipse([cx+4+flap,cy+2,cx+10,cy+8],fill=C['blue'],outline=C['dark_blue'])
    d.point((cx+7+flap,cy-3),fill=C['white']); d.point((cx+7+flap,cy+5),fill=C['white'])
    # 触角
    d.line([(cx,cy-6),(cx-2,cy-10)],fill=C['dark_brown'])
    d.line([(cx,cy-6),(cx+2,cy-10)],fill=C['dark_brown'])
    return img
def gen_butterfly():
    return[draw_butterfly(0,0),draw_butterfly(0,1),draw_butterfly(0,0),draw_butterfly(0,-1)]

# 28. bird_egg
def draw_bird_egg(dy=0):
    img,d=canvas(); cx,cy=24,24+dy
    d.ellipse([cx-10,cy-12,cx+10,cy+12],fill=C['white'],outline=C['light_brown'])
    d.ellipse([cx-6,cy-9,cx+4,cy-3],fill=C['light_brown'])
    # 斑点 ×4
    d.point((cx-3,cy-5),fill=C['mid_brown'])
    d.point((cx+2,cy-7),fill=C['mid_brown'])
    d.point((cx-1,cy+2),fill=C['mid_brown'])
    d.point((cx+4,cy+4),fill=C['mid_brown'])
    return img
def gen_bird_egg():
    return[draw_bird_egg(0),draw_bird_egg(-1),draw_bird_egg(0),draw_bird_egg(1)]

# 29. hatched
def draw_hatched(dy=0):
    img,d=canvas(); cx,cy=24,24+dy
    # 蛋壳下半
    d.arc([cx-10,cy-12,cx+10,cy+12],0,180,fill=C['white'])
    d.line([(cx-10,cy),(cx-6,cy+3)],fill=C['white'])
    d.line([(cx-2,cy),(cx+2,cy+3)],fill=C['white'])
    d.line([(cx+6,cy),(cx+10,cy+3)],fill=C['white'])
    # 小鸟头
    d.ellipse([cx-5,cy-8,cx+5,cy+2],fill=C['gold'],outline=C['orange'])
    # 眼睛
    d.point((cx-2,cy-4),fill=C['dark_brown'])
    d.point((cx-2,cy-5),fill=C['white'])
    # 嘴
    d.polygon([(cx+4,cy-3),(cx+8,cy-2),(cx+4,cy-1)],fill=C['orange'])
    return img
def gen_hatched():
    return[draw_hatched(0),draw_hatched(-1),draw_hatched(0),draw_hatched(1)]

# 30. flying
def draw_flying(dy=0,flap=0):
    img,d=canvas(); cx,cy=24,24+dy
    # 身体
    d.ellipse([cx-3,cy-4,cx+5,cy+6],fill=C['gold'],outline=C['orange'])
    # 头
    d.ellipse([cx-4,cy-7,cx+4,cy+1],fill=C['gold'],outline=C['orange'])
    # 眼睛
    d.point((cx-1,cy-4),fill=C['dark_brown'])
    d.point((cx-1,cy-5),fill=C['white'])
    # 嘴
    d.polygon([(cx+3,cy-3),(cx+7,cy-2),(cx+3,cy-1)],fill=C['orange'])
    # 左翅
    d.ellipse([cx-12,cy-2+flap,cx-2,cy+4+flap],fill=C['light_blue'],outline=C['dark_blue'])
    d.line([(cx-10,cy+1+flap),(cx-4,cy+1+flap)],fill=C['dark_blue'])
    # 右翅
    d.ellipse([cx+4,cy-2+flap,cx+14,cy+4+flap],fill=C['light_blue'],outline=C['dark_blue'])
    d.line([(cx+6,cy+1+flap),(cx+12,cy+1+flap)],fill=C['dark_blue'])
    # 尾巴
    d.polygon([(cx+4,cy+5),(cx+8,cy+7),(cx+4,cy+8)],fill=C['gold'],outline=C['orange'])
    return img
def gen_flying():
    return[draw_flying(0,0),draw_flying(0,-2),draw_flying(0,0),draw_flying(0,2)]

# 31. picked
def draw_picked(dy=0):
    img,d=canvas(); cx,cy=24,20+dy; pr=5
    # 花
    for i in range(5):
        a=math.radians(i*72-90)
        px=cx+int((pr+2)*math.cos(a)); py=cy+int((pr+2)*math.sin(a))
        d.ellipse([px-4,py-4,px+3,py+3],fill=C['red'],outline=C['dark_red'])
    d.ellipse([cx-3,cy-3,cx+2,cy+2],fill=C['gold'])
    # 茎
    d.line([(cx,cy+3),(cx+6,cy+16)],fill=C['mid_green'])
    # 手（3根手指）
    d.ellipse([cx+4,cy+14,cx+16,cy+24],fill=C['cream_brown'],outline=C['light_brown'])
    d.line([(cx+6,cy+16),(cx+2,cy+10)],fill=C['cream_brown'])
    d.line([(cx+8,cy+15),(cx+5,cy+9)],fill=C['cream_brown'])
    d.line([(cx+10,cy+15),(cx+8,cy+9)],fill=C['cream_brown'])
    return img
def gen_picked():
    return[draw_picked(0),draw_picked(-1),draw_picked(0),draw_picked(1)]

# 32. vase
def draw_vase(dy=0):
    img,d=canvas(); cx,cy=24,24+dy
    # 花瓶
    d.polygon([(cx-8,cy+4),(cx-6,cy+18),(cx+6,cy+18),(cx+8,cy+4)],fill=C['blue'],outline=C['dark_blue'])
    d.ellipse([cx-8,cy+3,cx+8,cy+8],fill=C['blue'],outline=C['dark_blue'])
    d.ellipse([cx-6,cy+4,cx+6,cy+7],fill=C['light_blue'])
    # 花瓶花纹
    d.arc([cx-6,cy+10,cx+6,cy+14],0,180,fill=C['ice_blue'])
    # 花茎
    d.line([(cx,cy+4),(cx,cy-10)],fill=C['mid_green'])
    # 花
    for i in range(5):
        a=math.radians(i*72-90)
        px=cx+int(7*math.cos(a)); py=cy-10+int(7*math.sin(a))
        d.ellipse([px-3,py-3,px+2,py+2],fill=C['red'],outline=C['dark_red'])
    d.ellipse([cx-2,cy-12,cx+2,cy-8],fill=C['gold'])
    return img
def gen_vase():
    return[draw_vase(0),draw_vase(-1),draw_vase(0),draw_vase(1)]

# ================================================================
# 主函数
# ================================================================
ALL_FORMS = [
    ('seed',gen_seed),('watered',gen_watered),('dry',gen_dry),('sunny',gen_sunny),
    ('shade',gen_shade),('rain_wait',gen_rain_wait),('ignored',gen_ignored),('scorched',gen_scorched),
    ('windowsill',gen_windowsill),('corner',gen_corner),('overwatered',gen_overwatered),('just_right',gen_just_right),
    ('sprout',gen_sprout),('withered',gen_withered),('rained',gen_rained),('flooded',gen_flooded),
    ('blown',gen_blown),('stepped',gen_stepped),('bloom',gen_bloom),('fruit',gen_fruit),
    ('corner_grow',gen_corner_grow),('rotten',gen_rotten),('seedling',gen_seedling),('rooted',gen_rooted),
    ('eaten_by_bug',gen_eaten_by_bug),('eaten_by_bird',gen_eaten_by_bird),('butterfly',gen_butterfly),('bird_egg',gen_bird_egg),
    ('hatched',gen_hatched),('flying',gen_flying),('picked',gen_picked),('vase',gen_vase),
]

if __name__=='__main__':
    print('='*56)
    print(f'  像素风素材生成器 — 全 {len(ALL_FORMS)} 形态 × 4 帧')
    print(f'  画布: {S}x{S}px | 调色板: {len(PALETTE)} 色')
    print(f'  输出: {OUT_DIR}')
    print('='*56)
    print()
    print('生成中...')
    for name,fn in ALL_FORMS:
        save(name,fn())
    print()
    print(f'完成! 共 {len(ALL_FORMS)} 个形态, {len(ALL_FORMS)*4} 帧 PNG + {len(ALL_FORMS)} 个 bin 文件。')

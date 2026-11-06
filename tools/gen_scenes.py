#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《种子生长模拟器》32 节点场景背景生成器
- 输出: scenes/scene_XX_名称.png (240x320, 中心留给种子 PNG)
- 总览: scenes/overview.png (8x4 缩略图)
依赖: pip install pillow
"""
from PIL import Image, ImageDraw
import math
import os

W, H = 240, 320
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenes')

# ==================== 调色板 ====================
G1 = (26, 58, 42); G2 = (45, 90, 61); G3 = (74, 124, 89); G4 = (123, 174, 127); G5 = (168, 213, 168)
B1 = (42, 26, 15); B2 = (61, 40, 23); B3 = (107, 68, 35); B4 = (139, 111, 71); B5 = (196, 167, 125)
R1 = (92, 31, 42); R2 = (139, 46, 61); R3 = (214, 69, 80); R4 = (244, 162, 97); R5 = (255, 217, 61)
C1 = (15, 36, 64); C2 = (30, 58, 95); C3 = (59, 130, 196); C4 = (126, 200, 227); C5 = (184, 230, 240)
WH = (255, 255, 255); KK = (42, 42, 62)
SKY_BOT = (42, 26, 62)
CLOUD_D = (58, 58, 78)          # 乌云 #3A3A4E
WALL_D = (30, 30, 46)           # 室内暗角

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def overlay(img, fn):
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(ov))
    return Image.alpha_composite(img, ov)

RND = None  # 每次渲染重置, 保证可复现

# ==================== 第 1 层: 天空 ====================
def sky_img(cfg):
    img = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(img)
    s = cfg.get('sky')
    if s[0] == 'solid':
        d.rectangle([0, 0, W, H], fill=s[1] + (255,))
    else:
        for y in range(H):
            d.line([(0, y), (W, y)], fill=lerp(s[1], s[2], y / H) + (255,))
    return img

# ==================== 第 2 层: 远景 ====================
STARS = [(18, 16), (48, 34), (70, 12), (96, 44), (120, 22), (146, 52), (168, 14),
         (222, 66), (30, 78), (86, 84), (140, 90), (206, 96), (58, 100), (178, 104)]

def draw_stars(d):
    for i, (x, y) in enumerate(STARS):
        if i % 4 == 0:
            d.rectangle([x - 1, y, x + 1, y], fill=WH + (255,))
            d.rectangle([x, y - 1, x, y + 1], fill=WH + (255,))
        else:
            d.point((x, y), fill=WH + (255,) if i % 3 else R5 + (255,))

def draw_moon(d):
    d.ellipse([28, 24, 52, 48], fill=R5 + (255,), outline=R4 + (255,))
    d.ellipse([36, 22, 58, 44], fill=C1 + (255,))   # 遮出月牙

def draw_sun(d, red=False):
    x, y = 196, 52
    body = R3 if red else R5
    edge = R1 if red else R4
    d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=body + (255,), outline=edge + (255,))
    for i in range(8):
        a = math.radians(i * 45)
        d.line([(x + int(16 * math.cos(a)), y + int(16 * math.sin(a))),
                (x + int(22 * math.cos(a)), y + int(22 * math.sin(a)))], fill=edge + (255,))

def draw_clouds(d, dark=False, white=False, positions=None):
    col = CLOUD_D if dark else (WH if white else C2)
    for (cx, cy) in (positions or [(60, 60), (170, 88)]):
        d.ellipse([cx - 20, cy - 6, cx + 2, cy + 8], fill=col + (255,))
        d.ellipse([cx - 8, cy - 10, cx + 14, cy + 6], fill=col + (255,))
        d.ellipse([cx + 2, cy - 5, cx + 22, cy + 8], fill=col + (255,))

def draw_window(d, dusk=False):
    d.rectangle([150, 48, 216, 140], fill=B3 + (255,))
    glass = (R4 if dusk else C4)
    d.rectangle([156, 54, 210, 134], fill=glass + (255,))
    if dusk:
        for y in range(54, 134):
            d.line([(156, y), (210, y)], fill=lerp(R4, R1, (y - 54) / 80) + (255,))
    d.line([(183, 54), (183, 134)], fill=B3 + (255,))
    d.line([(156, 94), (210, 94)], fill=B3 + (255,))
    if not dusk:   # 窗外云
        d.ellipse([160, 66, 180, 76], fill=WH + (255,))
        d.ellipse([188, 104, 208, 114], fill=WH + (255,))

# ==================== 第 3 层: 中景 ====================
def draw_ground(d, kind):
    top = 192
    if kind == 'floor':                      # 室内地板
        d.rectangle([0, 230, W, H], fill=B2 + (255,))
        for x in range(0, W, 40):
            d.line([(x, 230), (x + 10, H)], fill=B1 + (255,))
        d.line([(0, 230), (W, 230)], fill=B4 + (255,))
        return
    pairs = {'soil': (B2, B1), 'lit': (B3, B2), 'dry': (B4, B2),
             'char': (B1, B1), 'grass': (G3, G2), 'wet': (B2, B1)}
    a, b = pairs[kind]
    for y in range(top, H):
        d.line([(0, y), (W, y)], fill=lerp(a, b, (y - top) / (H - top)) + (255,))
    d.line([(0, top), (W, top)], fill=B4 + (255,) if kind in ('lit', 'dry') else B3 + (255,))
    for i in range(8):                       # 土壤纹理
        tx = 10 + (i * 61) % 210
        ty = top + 12 + (i * 37) % 90
        d.arc([tx, ty, tx + 8, ty + 4], 0, 180, fill=B1 + (255,))
    if kind != 'char':                       # 种子座位小土丘
        d.ellipse([96, top - 6, 144, top + 10], fill=a + (255,), outline=B1 + (255,))

def draw_cracks(d):
    for (x, y) in [(40, 220), (110, 250), (180, 215), (70, 285), (160, 290)]:
        d.line([(x, y), (x + 8, y + 6), (x + 6, y + 14)], fill=B1 + (255,))
        d.line([(x + 8, y + 6), (x + 16, y + 4)], fill=B1 + (255,))

def draw_wet_patches(d):
    for (x, y, w) in [(70, 210, 40), (140, 240, 50), (40, 270, 44)]:
        d.ellipse([x, y, x + w, y + 10], fill=B1 + (255,))

def draw_water(d, level, deep=False, ripples=False, bubbles=False, swirl=False):
    d.rectangle([0, level, W, H], fill=(C2 if deep else C3) + (255,))
    d.line([(0, level), (W, level)], fill=C4 + (255,))
    if ripples:
        for (x, y) in [(30, level + 14), (120, level + 26), (190, level + 12), (80, level + 44)]:
            d.arc([x, y, x + 16, y + 6], 180, 360, fill=C4 + (255,))
    if bubbles:
        for (x, y, r) in [(60, 250, 3), (90, 280, 2), (150, 260, 3), (180, 295, 2), (120, 300, 2)]:
            d.ellipse([x - r, y - r, x + r, y + r], outline=C5 + (255,))
    if swirl:
        for r in (6, 12, 18):
            d.arc([120 - r, 240 - r // 2, 120 + r, 240 + r // 2], 30, 300, fill=C4 + (255,))

def draw_grass_tufts(d, n=6, dark=False):
    c1 = G2 if dark else G3
    c2 = G3 if dark else G4
    for i in range(n):
        gx = 16 + (i * 83) % 210
        gy = 205 + (i * 47) % 90
        if 96 < gx < 148 and gy < 215:       # 避开种子座位
            gx += 60
        d.line([(gx, gy), (gx - 3, gy - 8)], fill=c1 + (255,))
        d.line([(gx, gy), (gx + 1, gy - 10)], fill=c2 + (255,))
        d.line([(gx, gy), (gx + 4, gy - 7)], fill=c1 + (255,))

def draw_flowers(d, n=4):
    for i in range(n):
        fx = 24 + (i * 97) % 190
        fy = 215 + (i * 53) % 80
        if 90 < fx < 150 and fy < 220:
            fx += 70
        d.line([(fx, fy + 3), (fx, fy + 12)], fill=G2 + (255,))
        for a in range(5):
            ang = math.radians(a * 72 - 90)
            d.ellipse([fx + int(4 * math.cos(ang)) - 2, fy + int(4 * math.sin(ang)) - 2,
                       fx + int(4 * math.cos(ang)) + 2, fy + int(4 * math.sin(ang)) + 2],
                      fill=R3 + (255,))
        d.ellipse([fx - 2, fy - 2, fx + 2, fy + 2], fill=R5 + (255,))

def draw_tree(d):
    d.rectangle([56, 150, 64, 196], fill=B2 + (255,))
    d.ellipse([24, 104, 96, 160], fill=G2 + (255,), outline=G1 + (255,))
    d.ellipse([34, 112, 74, 140], fill=G3 + (255,))

def draw_big_leaf(d):
    d.ellipse([50, 20, 190, 90], fill=G2 + (255,), outline=G1 + (255,))
    d.ellipse([70, 30, 150, 62], fill=G3 + (255,))
    d.line([(120, 26), (120, 86)], fill=G1 + (255,))
    d.line([(90, 44), (150, 50)], fill=G1 + (255,))
    d.line([(120, 86), (120, 110)], fill=G2 + (255,))

def draw_leaf_holes(d):
    d.ellipse([40, 140, 200, 230], fill=G2 + (255,), outline=G1 + (255,))
    d.line([(60, 185), (180, 185)], fill=G1 + (255,))
    for (x, y, r) in [(90, 165, 7), (140, 195, 9), (110, 210, 5)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=C2 + (255,))

def draw_nest(d):
    d.line([(40, 226), (200, 226)], fill=B2 + (255,))          # 树枝
    d.ellipse([86, 196, 154, 228], fill=B4 + (255,), outline=B2 + (255,))
    for i in range(5):
        d.arc([90 + i * 4, 200 + (i % 2) * 4, 140 - i * 3, 226], 0, 180, fill=B3 + (255,))
    d.ellipse([98, 196, 142, 212], fill=B2 + (255,))

def draw_table(d):
    d.rectangle([30, 236, 210, 250], fill=B4 + (255,), outline=B2 + (255,))
    d.rectangle([44, 250, 54, 300], fill=B3 + (255,))
    d.rectangle([186, 250, 196, 300], fill=B3 + (255,))
    d.line([(30, 240), (210, 240)], fill=B5 + (255,))

def draw_corner(d):
    d.rectangle([0, 0, 70, H], fill=WALL_D + (255,))
    d.line([(70, 0), (70, H)], fill=CLOUD_D + (255,))
    d.rectangle([0, 240, W, H], fill=B1 + (255,))
    d.line([(0, 240), (W, 240)], fill=B2 + (255,))

def draw_web(d):
    for r in range(8, 40, 8):
        d.arc([0, 0, r * 2, r * 2], 0, 90, fill=WH + (255,))
    for a in range(0, 91, 30):
        rad = math.radians(a)
        d.line([(0, 0), (int(38 * math.cos(rad)), int(38 * math.sin(rad)))], fill=WH + (255,))

# ==================== 第 5 层: 氛围 ====================
def draw_drops(d, n):
    for i in range(n):
        x = 60 + (i * 97) % 130
        y = 60 + (i * 53) % 90
        d.ellipse([x - 2, y - 2, x + 2, y + 3], fill=C4 + (255,), outline=C3 + (255,))
        d.point((x - 1, y - 1), fill=C5 + (255,))

def draw_rain(d, n):
    for i in range(n):
        x = 20 + (i * 137) % 200
        y = 30 + (i * 71) % 120
        d.line([(x, y), (x - 2, y + 8)], fill=C4 + (255,))

def draw_wind(d):
    for (y, ln) in [(140, 60), (170, 90), (200, 50)]:
        d.line([(20, y), (20 + ln, y)], fill=WH + (255,))
        d.line([(40, y + 4), (20 + ln - 14, y + 4)], fill=C5 + (255,))

def draw_smoke(d):
    for x in (100, 140):
        d.line([(x, 190), (x - 4, 170), (x + 2, 150), (x - 2, 130)], fill=CLOUD_D + (255,))

def draw_lightning(d):
    d.line([(120, 70), (112, 96), (124, 100), (110, 130)], fill=WH + (255,), width=2)

def draw_petals(d):
    for i in range(7):
        x = 20 + (i * 149) % 200
        y = 60 + (i * 89) % 200
        d.ellipse([x, y, x + 5, y + 3], fill=R3 + (255,))

def draw_rays(d):
    img_fn = lambda dr: [dr.line([(196, 52), (tx, ty)], fill=R5 + (50,))
                         for (tx, ty) in [(90, 150), (120, 160), (150, 150)]]
    return img_fn

def draw_shaft(d):
    d.polygon([(156, 60), (200, 60), (140, 230), (80, 230)], fill=R5 + (40,))

def draw_footprint(d):
    d.ellipse([150, 205, 166, 216], fill=B1 + (255,))
    d.ellipse([154, 220, 170, 231], fill=B1 + (255,))

def draw_bugs(d, n):
    for i in range(n):
        x = 100 + i * 40
        y = 175 + i * 20
        d.ellipse([x, y, x + 5, y + 3], fill=B1 + (255,))
        d.point((x + 5, y + 1), fill=B1 + (255,))

def draw_butterfly(d, x, y):
    d.ellipse([x - 8, y - 6, x - 1, y + 2], fill=C3 + (255,), outline=C2 + (255,))
    d.ellipse([x + 1, y - 6, x + 8, y + 2], fill=C3 + (255,), outline=C2 + (255,))
    d.point((x - 4, y - 2), fill=WH + (255,))
    d.point((x + 4, y - 2), fill=WH + (255,))
    d.line([(x, y - 4), (x, y + 2)], fill=B1 + (255,))

def draw_dew(d):
    for (x, y) in [(60, 205), (170, 210), (90, 230), (200, 240)]:
        d.point((x, y), fill=WH + (255,))

def draw_dots(img, color, n):
    col = {'gold': R5, 'green': G4}.get(color, R5)
    def fn(dr):
        for i in range(n):
            x = 50 + (i * 173) % 150
            y = 110 + (i * 97) % 110
            r = 2 if i % 2 else 1
            dr.ellipse([x - r, y - r, x + r, y + r], fill=col + (140,))
    return overlay(img, fn)

# ==================== 场景配置 (32 节点) ====================
NIGHT = ('grad', C1, SKY_BOT)
DAWN = ('grad', C2, R4)
DUSK = ('grad', R3, R1)
SCOR = ('grad', R1, B1)

SCENES = [
    ('seed',        dict(sky=NIGHT, moon=1, stars=1, ground='soil', dots='gold')),
    ('watered',     dict(sky=NIGHT, moon=1, stars=1, ground='wet', wet=1, drops=4)),
    ('dry',         dict(sky=NIGHT, moon=1, stars=1, ground='dry', cracks=1)),
    ('sunny',       dict(sky=DAWN, sun=1, rays=1, ground='lit', dots='gold')),
    ('shade',       dict(sky=('solid', C2), bigleaf=1, ground='soil')),
    ('rain_wait',   dict(sky=('solid', C2), dclouds=1, ground='soil', lightning=1)),
    ('ignored',     dict(sky=NIGHT, moon=1, stars=1, ground='soil', weeds=1)),
    ('scorched',    dict(sky=SCOR, red_sun=1, ground='char', cracks=1, smoke=1)),
    ('indoor',      dict(sky=('solid', KK), window='day', ground='floor')),
    ('overwatered', dict(sky=NIGHT, moon=1, stars=1, water=176, ripples=1)),
    ('underwatered',dict(sky=NIGHT, moon=1, stars=1, ground='dry', cracks=1, drops=2)),
    ('rained',      dict(sky=('solid', C2), dclouds=1, ground='wet', wet=1, rain=6)),
    ('no_rain',     dict(sky=('solid', C2), dclouds=1, ground='dry', cracks=1)),
    ('blown',       dict(sky=('solid', C2), wind=1, ground='soil')),
    ('stepped',     dict(sky=NIGHT, moon=1, stars=1, ground='soil', footprint=1)),
    ('just_right',  dict(sky=DAWN, sun=1, clouds=1, ground='lit', dew=1, dots='gold')),
    ('windowsill',  dict(sky=('solid', KK), window='day', shaft=1, ground='floor')),
    ('corner',      dict(sky=('solid', WALL_D), corner=1, web=1)),
    ('drowned',     dict(sky=NIGHT, moon=1, water=150, deep=1, bubbles=1, ripples=1)),
    ('perfect',     dict(sky=DAWN, sun=1, clouds=1, ground='wet', wet=1, dew=1, dots='gold')),
    ('sprout',      dict(sky=DAWN, sun=1, clouds=1, ground='grass', butterfly=1, dots='green')),
    ('seedling',    dict(sky=('solid', C4), sun=1, wclouds=1, ground='grass', butterfly=2, dots='gold')),
    ('flooded',     dict(sky=('solid', C2), dclouds=1, water=160, swirl=1, rain=5)),
    ('new_soil',    dict(sky=DAWN, sun=1, clouds=1, ground='lit', tufts=1, dots='gold')),
    ('bloom',       dict(sky=DUSK, sun=1, clouds=1, ground='grass', flowers=1, petals=1, dots='gold')),
    ('fruit',       dict(sky=('solid', C4), sun=1, wclouds=1, ground='grass', tree=1, butterfly=1, dots='gold')),
    ('eaten_bug',   dict(sky=('solid', C2), leafholes=1, bugs=2)),
    ('eaten_bird',  dict(sky=DAWN, sun=1, clouds=1, ground='lit')),
    ('bird_egg',    dict(sky=('solid', C2), nest=1)),
    ('hatched',     dict(sky=DAWN, sun=1, clouds=1, nest=1, dots='gold')),
    ('picked',      dict(sky=DUSK, sun=1, ground='grass', flowers=1, petals=1)),
    ('vase',        dict(sky=('solid', KK), window='dusk', table=1, petals=1, dots='gold')),
]

# ==================== 渲染 ====================
def render_scene(cfg):
    img = sky_img(cfg)
    d = ImageDraw.Draw(img)
    if cfg.get('stars'): draw_stars(d)
    if cfg.get('moon'): draw_moon(d)
    if cfg.get('sun'): draw_sun(d)
    if cfg.get('red_sun'): draw_sun(d, red=True)
    if cfg.get('clouds'): draw_clouds(d)
    if cfg.get('wclouds'): draw_clouds(d, white=True)
    if cfg.get('dclouds'): draw_clouds(d, dark=True)
    if cfg.get('window'): draw_window(d, dusk=cfg['window'] == 'dusk')
    if cfg.get('corner'): draw_corner(d)
    if cfg.get('web'): draw_web(d)
    if cfg.get('ground'): draw_ground(d, cfg['ground'])
    if cfg.get('cracks'): draw_cracks(d)
    if cfg.get('wet'): draw_wet_patches(d)
    if isinstance(cfg.get('water'), int):
        draw_water(d, cfg['water'], cfg.get('deep'), cfg.get('ripples'),
                   cfg.get('bubbles'), cfg.get('swirl'))
    if cfg.get('weeds'): draw_grass_tufts(d, 8, dark=True)
    if cfg.get('tufts'): draw_grass_tufts(d, 5)
    if cfg.get('ground') == 'grass': draw_grass_tufts(d, 8)
    if cfg.get('flowers'): draw_flowers(d)
    if cfg.get('tree'): draw_tree(d)
    if cfg.get('bigleaf'): draw_big_leaf(d)
    if cfg.get('leafholes'): draw_leaf_holes(d)
    if cfg.get('nest'): draw_nest(d)
    if cfg.get('table'): draw_table(d)
    if cfg.get('drops'): draw_drops(d, cfg['drops'])
    if cfg.get('rain'): draw_rain(d, cfg['rain'])
    if cfg.get('wind'): draw_wind(d)
    if cfg.get('smoke'): draw_smoke(d)
    if cfg.get('lightning'): draw_lightning(d)
    if cfg.get('petals'): draw_petals(d)
    if cfg.get('footprint'): draw_footprint(d)
    if cfg.get('bugs'): draw_bugs(d, cfg['bugs'])
    if cfg.get('butterfly'):
        for i in range(cfg['butterfly']):
            draw_butterfly(d, 60 + i * 110, 120 + i * 30)
    if cfg.get('dew'): draw_dew(d)
    if cfg.get('rays'):
        img = overlay(img, draw_rays(None))
        d = ImageDraw.Draw(img)
    if cfg.get('shaft'):
        img = overlay(img, lambda dr: draw_shaft(dr))
        d = ImageDraw.Draw(img)
    if cfg.get('dots'):
        img = draw_dots(img, cfg['dots'], 5)
    return img

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    thumbs = []
    for i, (name, cfg) in enumerate(SCENES, 1):
        img = render_scene(cfg).convert('RGB')
        img.save(os.path.join(OUT, f'scene_{i:02d}_{name}.png'))
        thumbs.append((name, img))
        print(f'  [OK] {i:02d} {name}')
    # 总览图 8x4
    tw, th = 60, 80
    ov = Image.new('RGB', (tw * 8 + 18, th * 4 + 18), (10, 10, 11))
    for i, (name, img) in enumerate(thumbs):
        t = img.resize((tw, th), Image.NEAREST)
        x = 3 + (i % 8) * (tw + 2)
        y = 3 + (i // 8) * (th + 2)
        ov.paste(t, (x, y))
    ov.save(os.path.join(OUT, 'overview.png'))
    print('完成: %d 个场景 + overview.png' % len(SCENES))

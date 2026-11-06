#!/usr/bin/env python3
"""把 gen_sprites.py 生成的 48x48 RGBA PNG 转成固件内嵌的 RGB565A8 C 数组。

输出: main/seed_assets_data.{c,h}
布局(LVGL_COLOR_FORMAT_RGB565A8): 每帧 = RGB565 小端平面(w*h*2B) + A8 平面(w*h*1B)。
透明像素(alpha<128)的 RGB 分量写 0。
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, 'sprites_assets')
OUT_DIR = os.path.join(HERE, '..', 'main')

PALETTE_HEX = [
    '1A3A2A', '2D5A3D', '4A7C59', '7BAE7F',
    '3D2817', '6B4423', '8B6F47', 'C4A77D',
    '8B2E3D', 'D64550', 'F4A261', 'FFD93D',
    '1E3A5F', '3B82C4', '7EC8E3', 'B8E6F0',
    '2A2A3E', 'FFFFFF',
]

FORMS = [
    'seed', 'watered', 'dry', 'sunny', 'shade', 'rain_wait', 'ignored', 'scorched',
    'windowsill', 'corner', 'overwatered', 'just_right', 'sprout', 'withered', 'rained',
    'flooded', 'blown', 'stepped', 'bloom', 'fruit', 'corner_grow', 'rotten', 'seedling',
    'rooted', 'eaten_by_bug', 'eaten_by_bird', 'butterfly', 'bird_egg', 'hatched', 'flying',
    'picked', 'vase',
]

W = H = 48
FRAMES = 4
FRAME_BYTES = W * H * 3          # 2304*2 + 2304*1


def load_palette():
    pal = {}
    for hx in PALETTE_HEX:
        rgb = tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))
        rgb565 = ((rgb[0] & 0xF8) << 8) | ((rgb[1] & 0xFC) << 3) | (rgb[2] >> 3)
        pal[rgb] = rgb565
    return pal


def nearest(pal, px):
    if px in pal:
        return pal[px]
    best, bd = None, 1 << 30
    for rgb, v565 in pal.items():
        d = (px[0] - rgb[0]) ** 2 + (px[1] - rgb[1]) ** 2 + (px[2] - rgb[2]) ** 2
        if d < bd:
            bd, best = d, v565
    return best


def convert_frame(png_path, pal):
    from PIL import Image
    img = Image.open(png_path).convert('RGBA')
    assert img.size == (W, H), f'{png_path}: {img.size}'
    px = img.load()
    rgb = bytearray(W * H * 2)
    alpha = bytearray(W * H)
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            i = y * W + x
            if a < 128:
                alpha[i] = 0
            else:
                v = nearest(pal, (r, g, b))
                rgb[i * 2] = v & 0xFF
                rgb[i * 2 + 1] = (v >> 8) & 0xFF
                alpha[i] = 255
    return bytes(rgb) + bytes(alpha)


def main():
    from PIL import Image  # noqa: F401  提前报错,别写一半才发现没装
    pal = load_palette()
    decls, defs = [], []
    for form in FORMS:
        for f in range(FRAMES):
            path = os.path.join(IN_DIR, form, f'frame_{f}.png')
            data = convert_frame(path, pal)
            assert len(data) == FRAME_BYTES
            name = f'seed_img_{form}_f{f}'
            decls.append(f'extern const uint8_t {name}[{FRAME_BYTES}];')
            lines = [f'// {form} frame {f} (RGB565 + A8)']
            lines.append(f'const uint8_t {name}[{FRAME_BYTES}] = {{')
            for off in range(0, FRAME_BYTES, 16):
                chunk = data[off:off + 16]
                lines.append('    ' + ''.join(f'0x{b:02X},' for b in chunk))
            lines.append('};')
            defs.append('\n'.join(lines))
            print(f'  [OK] {form}_f{f}')

    table = 'const uint8_t *const seed_frames[SEED_FORM_COUNT][SEED_FRAME_COUNT] = {\n'
    for form in FORMS:
        row = ', '.join(f'seed_img_{form}_f{f}' for f in range(FRAMES))
        table += f'    {{ {row} }},\n'
    table += '};'

    h = '\n'.join([
        '// 本文件由 tools/convert_sprites.py 从 tools/sprites_assets/ 自动生成, 请勿手改。',
        '// 素材来源: gen_sprites.py (48x48, 18 色, RGBA)。',
        '#pragma once',
        '',
        '#include <stdint.h>',
        '',
        '#define SEED_FORM_COUNT 32',
        '#define SEED_FRAME_COUNT 4',
        f'#define SEED_IMG_W {W}',
        f'#define SEED_IMG_H {H}',
        f'#define SEED_FRAME_BYTES {FRAME_BYTES}',
        '',
        *decls,
        '',
        '// 形态索引表: [form][frame] 指向 RGB565A8 像素数组(RGB565 平面 + A8 平面)',
        f'extern const uint8_t *const seed_frames[SEED_FORM_COUNT][SEED_FRAME_COUNT];',
        '',
    ])
    c = '\n'.join([
        '// 本文件由 tools/convert_sprites.py 自动生成, 请勿手改。',
        '#include "seed_assets_data.h"',
        '',
        *defs,
        '',
        table,
        '',
    ])
    with open(os.path.join(OUT_DIR, 'seed_assets_data.h'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(h)
    with open(os.path.join(OUT_DIR, 'seed_assets_data.c'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(c)
    print(f'done: {len(FORMS)} forms x {FRAMES} frames, {FRAME_BYTES} B/frame')


if __name__ == '__main__':
    main()

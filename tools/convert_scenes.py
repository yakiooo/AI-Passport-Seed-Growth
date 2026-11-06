#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 32 个场景背景 + 封面 GIF 编码成固件内嵌的 RLE 索引图。

输出: main/scene_data.{c,h}
格式(scene_codec.c 消费, 全部小端):
  0..3   'S','R','L','E'
  4..5   w (u16)
  6..7   h (u16)
  8..9   npal (u16, 调色板项数)
  10..   palette npal * 2 字节 (RGB565 LE)
  ..     行偏移表 h * 2 字节 (u16, 相对行数据区起点)
  ..     行数据: 每行若干 (count u8>=1, palette_idx u8) 游程, 覆盖整行宽

为什么不用 LVGL 的 I4/I8: 内建解码器会把索引图整图转成 ARGB8888 进 RAM
(240x320 -> 300KB), 直接把堆打爆。自编码 + 自定义解码器逐行出图, RAM 只占一行。
"""
import importlib.util
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, '..', 'main')
GIF_PATH = r'C:\Users\yako0\Desktop\种子生长模拟器_封面.gif'

# ---- 复用 gen_scenes.py 的渲染逻辑(纯函数, import 不落盘) ----
spec = importlib.util.spec_from_file_location('gen_scenes', os.path.join(HERE, 'gen_scenes.py'))
gen_scenes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_scenes)


def rgb565(rgb):
    r, g, b = rgb
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def encode_rle(img):
    """RGB PIL Image -> RLE 字节串(格式见文件头注释)。"""
    w, h = img.size
    q = img.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    idx = q.tobytes()                                  # 每像素一个调色板索引
    pal = q.getpalette()[:256 * 3]
    # 实际用到的最高索引决定调色板项数
    npal = max(idx) + 1

    rows = []
    off = 0
    rowtab = []
    body = bytearray()
    for y in range(h):
        rowtab.append(len(body))
        row = idx[off:off + w]
        off += w
        prev = row[0]
        cnt = 1
        for v in row[1:]:
            if v == prev and cnt < 255:
                cnt += 1
            else:
                body.append(cnt)
                body.append(prev)
                prev = v
                cnt = 1
        body.append(cnt)
        body.append(prev)

    out = bytearray()
    out += b'SRLE'
    out += struct.pack('<HHH', w, h, npal)
    for i in range(npal):
        out += struct.pack('<H', rgb565(pal[i * 3:i * 3 + 3]))
    for o in rowtab:
        out += struct.pack('<H', o)
    out += body
    return bytes(out), npal


def decode_rle(data):
    """回放校验: RLE -> RGB PIL Image, 与编码端无依赖地独立实现。"""
    assert data[:4] == b'SRLE'
    w, h, npal = struct.unpack_from('<HHH', data, 4)
    pal565 = struct.unpack_from('<%dH' % npal, data, 10)
    pal = [(c >> 8 & 0xF8, c >> 3 & 0xFC, (c & 0x1F) << 3) for c in pal565]
    rowtab = struct.unpack_from('<%dH' % h, data, 10 + npal * 2)
    base = 10 + npal * 2 + h * 2
    img = Image.new('RGB', (w, h))
    px = img.load()
    for y in range(h):
        p = base + rowtab[y]
        x = 0
        while x < w:
            cnt, ci = data[p], data[p + 1]
            p += 2
            for _ in range(cnt):
                px[x, y] = pal[ci]
                x += 1
    return img


def emit(name, blobs, f_c, f_h, comment):
    f_h.write('extern const uint8_t %s[%d];\n' % (name, len(blobs)))
    f_c.write('// %s (%d bytes)\n' % (comment, len(blobs)))
    f_c.write('const uint8_t %s[%d] = {' % (name, len(blobs)))
    for i, b in enumerate(blobs):
        if i % 16 == 0:
            f_c.write('\n    ')
        f_c.write('0x%02X,' % b)
    f_c.write('\n};\n\n')


def main():
    scenes = []
    for i, (name, cfg) in enumerate(gen_scenes.SCENES, 1):
        img = gen_scenes.render_scene(cfg).convert('RGB')
        blobs, npal = encode_rle(img)
        scenes.append((i, name, blobs))
        print('  scene %02d %-12s %6d B (%d 色)' % (i, name, len(blobs), npal))

    covers = []
    gif = Image.open(GIF_PATH)
    for f in range(gif.n_frames):
        gif.seek(f)
        frame = gif.convert('RGB')
        blobs, npal = encode_rle(frame)
        covers.append(blobs)
        print('  cover frame %d      %6d B (%d 色)' % (f, len(blobs), npal))

    total = sum(len(b) for _, _, b in scenes) + sum(len(b) for b in covers)
    print('合计: %d B (%.0f KB)' % (total, total / 1024))

    with open(os.path.join(OUT_DIR, 'scene_data.c'), 'w', encoding='utf-8') as fc, \
         open(os.path.join(OUT_DIR, 'scene_data.h'), 'w', encoding='utf-8') as fh:
        fc.write('// 本文件由 tools/convert_scenes.py 生成, 请勿手改。\n')
        fc.write('// 自定义 RLE 索引图, 由 main/scene_codec.c 的解码器逐行解码为 RGB565。\n')
        fc.write('#include "scene_data.h"\n\n')
        fh.write('#pragma once\n\n#include <stdint.h>\n\n')
        fh.write('#define SCENE_COUNT %d\n#define COVER_FRAME_COUNT %d\n\n' %
                 (len(scenes), len(covers)))
        for i, name, blobs in scenes:
            emit('scene_rle_%02d' % i, blobs, fc, fh, '场景 %02d %s' % (i, name))
        for f, blobs in enumerate(covers):
            emit('cover_rle_%d' % f, blobs, fc, fh, '封面 GIF 第 %d 帧' % f)

        fc.write('const uint8_t *const SCENE_RLE[SCENE_COUNT] = {\n')
        for i, _, _ in scenes:
            fc.write('    scene_rle_%02d,\n' % (i))
        fc.write('};\n\n')
        fc.write('const uint8_t *const COVER_RLE[COVER_FRAME_COUNT] = {\n')
        for f in range(len(covers)):
            fc.write('    cover_rle_%d,\n' % f)
        fc.write('};\n')
        fh.write('\nextern const uint8_t *const SCENE_RLE[SCENE_COUNT];\n')
        fh.write('extern const uint8_t *const COVER_RLE[COVER_FRAME_COUNT];\n')

    # 回放校验 + 预览拼图
    prev_dir = os.path.join(HERE, 'scene_preview')
    os.makedirs(prev_dir, exist_ok=True)
    for i, name, blobs in scenes:
        back = decode_rle(blobs)
        src = gen_scenes.render_scene(gen_scenes.SCENES[i - 1][1]).convert('RGB')
        diff = sum(1 for a, b in zip(back.tobytes(), src.tobytes()) if abs(a - b) > 24)
        if diff > src.size[0] * src.size[1] * 0.02:
            print('  [WARN] scene %02d 回放差异像素较多: %d' % (i, diff))
        back.save(os.path.join(prev_dir, 'scene_%02d.png' % i))
    for f, blobs in enumerate(covers):
        decode_rle(blobs).save(os.path.join(prev_dir, 'cover_%d.png' % f))
    print('回放校验完成, 预览在 tools/scene_preview/')


if __name__ == '__main__':
    main()

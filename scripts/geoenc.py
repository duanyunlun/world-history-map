#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
几何压缩：把 SVG 路径字符串（M x y L x y … Z）转成 base64 变长整数编码。

编码格式（每条路径一个字符串）：
  依次为若干环，每环以 varint 记录点数，随后按点记录 x/y 的增量（zigzag varint），
  坐标以 0.1 单位为整数（与生成时 %.1f 精度一致）。
解码在前端完成（src/app.js 的 geomPath），只解码一次并缓存。
"""
import base64
import re

_NUM = re.compile(r'-?\d+\.?\d*')
_RING = re.compile(r'M([^MZ]*)Z?')


def _varint(buf, v):
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            buf.append(b | 0x80)
        else:
            buf.append(b)
            break


def _zig(v):
    return (v << 1) ^ (v >> 31) if v >= 0 else ((-v) << 1) - 1


def encode_d(d, prec=10):
    """把 'M…Z' 路径字符串编码为紧凑串；返回 (编码串, 点数)"""
    buf = bytearray()
    total = 0
    for m in _RING.finditer(d or ''):
        nums = _NUM.findall(m.group(1))
        n = len(nums) // 2
        if n < 3:
            continue
        _varint(buf, n)
        px = py = 0
        for i in range(n):
            x = int(round(float(nums[2 * i]) * prec))
            y = int(round(float(nums[2 * i + 1]) * prec))
            _varint(buf, _zig(x - px))
            _varint(buf, _zig(y - py))
            px, py = x, y
        total += n
    return base64.b64encode(bytes(buf)).decode('ascii'), total


def encode_paths(obj, keys=('d',)):
    """就地压缩字典/列表中的路径字段：把 obj[k] 换成 obj['c']，并删除原字段"""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k]:
                c, n = encode_d(obj[k])
                obj['c'] = c
                obj['n'] = n
                del obj[k]
        return obj
    return obj


if __name__ == '__main__':
    import sys
    d = 'M1.0 2.0L3.5 4.5L6.0 2.0Z'
    c, n = encode_d(d)
    print('样例：', d, '→', c, '点数', n, '原长', len(d), '压缩后', len(c))

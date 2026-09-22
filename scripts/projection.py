#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投影的唯一真相源（Single Source of Truth）。

为什么单独成模块：中国图层与世界图层此前各自实现了一份投影公式（虽然当时数值一致，
但属于"靠人记住保持一致"的隐式契约）。一旦有人改了其中一处，两层就会错位——
本项目已经因为"隐式契约"栽过多次（势力键撞名、命名对不上、区间重叠）。

现在：两个构建脚本都从这里取投影与画布参数；构建产物把投影名与参数写进 world.meta，
前端据此实现同一公式（src/app.js 的 wproj）。**改投影只改这一个文件。**

当前选择：等距圆柱（Equirectangular / Plate Carrée）
  x = cx + lon·k,  y = cy − lat·k      （k = scale·π/180）
  经线垂直、纬线水平——真正的"平面地图"，放大到任意区域都不会有球面感。
  代价：高纬度东西向拉伸（赤道 1×，35°N 约 1.22×，60°N 约 2×），极区更明显；
  历史地图以中低纬文明为主，这个代价可接受。若将来想减轻极区失真，
  只改本文件（换成 Miller 等），两端自动一致。
"""
import math

PROJECTION = 'Equirectangular'
SCALE = 417.0             # 世界宽 = 360°·(π/180)·417 ≈ 2620 单位（与旧画布尺寸一致）
CX, CY = 1310.0, 700.0    # 画布中心
RAD = math.pi / 180.0


def project(lon, lat):
    """经纬度 → 画布坐标（等距圆柱）。未投影的原始值也一并返回，便于需要时改用。"""
    return (CX + lon * RAD * SCALE, CY - lat * RAD * SCALE)


def meta():
    return {'projection': PROJECTION, 'scale': SCALE, 'cx': CX, 'cy': CY}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包便携分发版（单文件）。

产出：
  dist/世界历史地图-前10000-2026.zip   一个自包含的 index.html + 使用说明.txt
  dist/SHA256SUMS.txt               校验和

index.html 内联了全部地图几何、史料数据与逻辑：双击即可离线打开，
不联网、不依赖任何外部资源，可直接转发给朋友。

用法：
  python3 release.py             # 重新构建后打包
  python3 release.py --no-build  # 用现有 index.html 打包
"""
import os, sys, shutil, zipfile, hashlib, subprocess, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
NAME = '世界历史地图-前10000-2026'

README_TXT = """世界历史地图 · 前10000 — 2026（动态势力范围）
================================================

【怎么打开】
  双击 index.html 即可（Chrome / Edge / Safari）。完全离线：地图几何、史料、人物资料
  全部打包在这一个文件里，不联网、不装软件、不向外部发送任何数据，可直接转发。

【时间轴：可变步长】
  底部区间按钮决定步长，拖动滑块或按 ‹ › 步进：
    · 史前 / 上古                         —— 世界图层（千年—数百年一跳）
    · 商周·逐年（前1600—前771）          —— 中国逐年（另有世界同期底图）
    · 春秋战国·逐年（前770—前221）
    · 秦汉·逐年（前220—公元219）
    · 三国两晋南北朝·逐年（220—617）
    · 隋唐五代·逐年（618—959）
    · 宋辽夏金·逐年（960—1270）
    · 元 / 明 / 清·逐年（1271—1892）
    · 中国近代·逐月（1893—1976）        —— 月度精度，1008 个月
    · 当代（1977—2026）
  空格键自动播放，← → 前后一步（按住 Shift 跨年），Esc 返回上级。

【怎么用】
  1) 地图按「该时期各地实际控制政权／势力」着色，拖动时间轴即可看到疆域变化。
     中国部分：清 → 军阀割据 → 南京国民政府 → 日伪与抗日根据地并存 →
     中华人民共和国成立 → 西藏和平解放 等，按月变化。
  2) 点击任意省份（中国区）或任意政体色块（世界区）：镜头拉近，右侧展开详情
     （当月归属及依据、当月事件、前后事件、势力变迁时间表）。
  3) 点击事件（地图光点或右侧卡片）：展开事件详情（时间、地点、当时势力、
     详细时间线、影响、相关人物），每条事件都附可点击来源链接。
  4) 点击人物名：同页跳转人物生平，生平中的事件可再点回。
  5) 右上角「检索」：可搜政体（中英文名）、事件、中国省份；选中即切换年代并定位。
  6) 左上角「全球／东亚／欧洲…」：一键飞到该区域。

【数据与口径（重要）】
  · 中国省级归属以「省级单元该时期的实际控制」为准；政权交错地带标注主要控制方，
    地块悬停或看右侧「归属依据」可见判定说明。
  · 商周至宋辽夏金等早期时期，古代政区（王畿/诸侯/郡县/州/道/路/行省）与今省界
    没有对应关系：这些时期沿用今省界，只以色块表示「主要控制或文化归属」，
    仅供大势参考，具体疆界请以考古与出土文献为准。
  · 底板采用现行省界，仅供定位；历史省界变动（热河、察哈尔、绥远、西康、内蒙古分隶等）
    均按实际撤并月份处理，并在事件正文中说明。
  · 世界政治边界随时间变化：前1886 年取自 historical-basemaps 的 54 个时间切片，
    1886—2019 年为 CShapes 逐年边界，2011 年后为 Natural Earth 现行国界。
    世界部分不追求县级精度，按史料记载的政权范围呈现。
  · 事件时间以史料记载为准，仅记到年月者标注「月份待考」。
  · 涉台、涉藏表述采用公开出版物规范用语；南海诸岛以标准角标示意。

【数据来源与许可】
  · historical-basemaps（aourednik）—— GPL-3.0，用于公元 1886 年以前的世界政治边界。
  · CShapes 2.0（ETH Zürich）—— 学术免费使用，用于 1886—2019 年逐年国界。
  · Natural Earth（50m）—— 公有领域，用于现代国界与底图。
  · 中国部分：以公开出版物与公开网页资料整理（《中国历史地图集》近现代部分、
    各省地方志、党史与民国史公开研究等），每个事件均附可点击来源链接。
  · 本作品同样以 GPL-3.0 兼容方式提供；再分发请保留本说明与来源标注。

【已知限制】
  · 世界图层在 1886 年前的切片较疏（按世纪/数百年），不宜用于精确边界比对。
  · 公元前 1600 年以前的中国区域仅由世界图层呈现，未绘制中国政区（避免臆造）。
  · 政体详情的「存续期」在无专门条目时由边界数据出现的年份区间推得，仅供参考。

【提示】
  · 建议窗口 1280×800 以上；窗口越大，地图与右侧说明越舒展。
  · 仅供历史学习与教学演示，引用请保留来源标注。
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    if '--no-build' not in sys.argv:
        print('→ 构建站点 …')
        subprocess.run([sys.executable, 'build.py'], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    idx = os.path.join(ROOT, 'index.html')
    if not os.path.exists(idx):
        print('!! 缺少 index.html'); sys.exit(1)

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, NAME + '.zip')
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(idx, os.path.join(tmp, 'index.html'))
        with open(os.path.join(tmp, '使用说明.txt'), 'w', encoding='utf-8') as f:
            f.write(README_TXT)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(os.path.join(tmp, 'index.html'), os.path.join(NAME, 'index.html'))
            z.write(os.path.join(tmp, '使用说明.txt'), os.path.join(NAME, '使用说明.txt'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    digest = sha256(out)
    with open(os.path.join(DIST, 'SHA256SUMS.txt'), 'w', encoding='utf-8') as f:
        f.write('%s  %s\n' % (digest, os.path.basename(out)))

    # 自检：压缩包内 index.html 与站点一致
    with zipfile.ZipFile(out) as z:
        inside = z.read(os.path.join(NAME, 'index.html'))
    same = hashlib.sha256(inside).hexdigest() == sha256(idx)
    print('\n单文件站点 : index.html  %.2f MB' % (os.path.getsize(idx) / 1048576))
    print('分发包     : %s  %.2f MB' % (os.path.basename(out), os.path.getsize(out) / 1048576))
    print('包内校验   : %s' % ('一致 ✓' if same else '不一致 ✗'))
    print('SHA256     : %s' % digest)
    print('\n把 dist/%s 直接发给朋友即可（解压后双击 index.html）。' % os.path.basename(out))


if __name__ == '__main__':
    main()

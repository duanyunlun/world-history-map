#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S7 静态站点输出：把构建好的单文件地图放到 site/，供 GitHub Pages 等静态托管。

为什么单独一步：index.html 在 .gitignore 里（它是构建产物，可重建），
而静态托管需要仓库里真的有页面文件。所以由本脚本产出 **入库的 site/** 目录，
既保留"产物不进主目录"的规范，又满足托管需要。

用法：
  python3 scripts/build_site.py            # 产出 site/index.html
  python3 scripts/build_site.py --check    # 只校验 site/ 是否与当前构建一致
"""
import hashlib, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'index.html')
SITE = os.path.join(ROOT, 'site')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    if not os.path.exists(SRC):
        print('✗ 未找到 index.html，请先运行 python3 build.py')
        sys.exit(1)
    dst = os.path.join(SITE, 'index.html')
    check = '--check' in sys.argv
    if check:
        if not os.path.exists(dst):
            print('✗ site/index.html 不存在（需运行 scripts/build_site.py）')
            sys.exit(1)
        same = sha(SRC) == sha(dst)
        print('site/index.html 与当前构建%s（%s）' % ('一致' if same else '**不一致**', sha(SRC)[:12]))
        sys.exit(0 if same else 1)

    os.makedirs(SITE, exist_ok=True)
    shutil.copy2(SRC, dst)
    # 静态托管用：关掉 Jekyll 处理，避免 README 被当成首页
    open(os.path.join(SITE, '.nojekyll'), 'w').write('')
    # 根目录 .nojekyll：GitHub Pages 从根目录托管时，避免 Jekyll 把 README 当首页
    open(os.path.join(ROOT, '.nojekyll'), 'w').write('')
    print('✓ 已产出 site/index.html（%.1f MB）+ site/.nojekyll + 根目录 .nojekyll'
          % (os.path.getsize(dst) / 1048576))
    print('  托管：GitHub Pages 源=branch main / 根目录；本地预览：cd site && python3 -m http.server 8080')


if __name__ == '__main__':
    main()

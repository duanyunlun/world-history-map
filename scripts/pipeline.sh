#!/usr/bin/env bash
# 一条命令跑完：数据校验 → 构建 → 自检 → 真实鼠标 → 部署 → 打包
#
#   scripts/pipeline.sh              # 常规：校验 + 构建 + 测试 + 部署 + 打包
#   scripts/pipeline.sh --geo        # 额外重建中国几何（改过 historical_units/territories 时）
#   scripts/pipeline.sh --world      # 额外重建世界切片（改过 counties/neighbors 缓存时）
#   scripts/pipeline.sh --no-deploy  # 跳过 Docker 与打包（快速迭代）
#
# 之所以固化成脚本：此前多次出现「先验证后构建」「改了数据没重跑 build_geo」这类
# 时序错误，导致验证的其实是旧产物。顺序写死在这里，就不必再靠记忆。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

GEO=0; WORLD=0; DEPLOY=1
for a in "$@"; do
  case "$a" in
    --geo) GEO=1 ;;
    --world) WORLD=1 ;;
    --no-deploy) DEPLOY=0 ;;
  esac
done

step() { printf '\n=== %s ===\n' "$1"; }
fail() { printf '\n✗ %s\n' "$1"; exit 1; }

# 本地静态服务：验证依赖它，缺失则自动拉起（曾因服务挂掉把环境问题误判成代码问题）
if ! curl -sf -o /dev/null "http://127.0.0.1:8777/index.html"; then
  echo "· 本地静态服务未运行，启动 8777 …"
  (cd "$(pwd)" && nohup python3 -m http.server 8777 --bind 127.0.0.1 >/tmp/http8777.log 2>&1 &)
  sleep 2
  curl -sf -o /dev/null "http://127.0.0.1:8777/index.html" || fail "无法启动本地静态服务（8777）"
fi

step "0/6 数据清单（角色与读写关系）"
python3 scripts/manifest.py || fail "数据清单校验未通过（有文件未定性或源数据被构建脚本写入）"

step "0.5/6 架构守卫（每个关注点只能有一个权威实现）"
python3 scripts/check_arch.py || fail "架构守卫未通过（出现了第二套实现）"

step "1/6 数据校验"
python3 scripts/check_data.py || fail "数据校验未通过"

if [ "$WORLD" = "1" ]; then
  step "2/6 重建世界切片（build_world.py）"
  python3 build_world.py || fail "世界切片构建失败"
else
  step "2/6 世界切片（跳过，用 --world 才重建）"
fi

if [ "$GEO" = "1" ] || [ "$WORLD" = "1" ]; then
  step "3/6 重建中国几何（build_geo.py）"
  python3 build_geo.py || fail "中国几何构建失败"
else
  step "3/6 中国几何（跳过，用 --geo 才重建）"
fi

step "4/6 生成单文件（build.py）"
python3 build.py || fail "构建失败"

step "5/6 自检 + 真实鼠标"
SELF=$(node scripts/cdp_check.js "http://127.0.0.1:8777/tests/self_test.html?s=y1949&zoom=1" 300000)
echo "$SELF" | grep -E "TESTDONE|自检结果" || fail "自检未运行（先确认本地 8777 静态服务在跑）"
# fails>0 必须中断：此前脚本只匹配 TESTDONE 行，失败也会被当成通过
if ! echo "$SELF" | grep -q "TESTDONE fails=0"; then
  echo "$SELF" | grep -A2 "自检结果" | tail -2
  fail "自检存在失败项"
fi
node scripts/verify_click.js "http://127.0.0.1:8777/index.html" | tail -2 || fail "真实鼠标验证未通过"

if [ "$DEPLOY" = "1" ]; then
  step "6/6 部署与打包"
  docker compose up -d --build >/dev/null 2>&1 && sleep 14
  node scripts/verify_click.js "http://localhost:8780/" | tail -2 || fail "容器验证未通过"
  python3 scripts/build_site.py | tail -2
  python3 release.py | tail -2
else
  step "6/6 部署与打包（跳过）"
fi

printf '\n✓ 全部通过\n'

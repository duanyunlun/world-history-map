#!/usr/bin/env bash
# 用无头 Edge/Chrome 对页面截图
# 用法: bash scripts/shot.sh <url> <out.png> [width] [height] [waitMs]
set -euo pipefail
URL="${1:?用法: shot.sh <url> <out.png> [width] [height] [waitMs]}"
OUT="${2:?缺少输出路径}"
W="${3:-1400}"; H="${4:-900}"; WAIT="${5:-12000}"
BROWSER=""
for c in "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "$(command -v chromium 2>/dev/null || true)" \
         "$(command -v google-chrome 2>/dev/null || true)"; do
  [ -x "$c" ] && BROWSER="$c" && break
done
[ -z "$BROWSER" ] && { echo "未找到可用的 Chromium 内核浏览器"; exit 1; }
"$BROWSER" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --virtual-time-budget="$WAIT" --window-size="$W,$H" --screenshot="$OUT" "$URL" >/dev/null 2>&1
echo "已截图: $OUT"

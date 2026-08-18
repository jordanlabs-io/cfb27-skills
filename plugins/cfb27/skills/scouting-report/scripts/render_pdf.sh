#!/bin/bash
# Render an HTML brief to PDF via headless Chromium (no install required if a
# Playwright browser cache exists). Usage: render_pdf.sh <in.html> <out.pdf>
set -euo pipefail
IN="$1"; OUT="$2"

find_chrome() {
  # Newest Playwright-cached Chromium (macOS), then common fallbacks.
  local c
  c=$(ls -d "$HOME/Library/Caches/ms-playwright"/chromium-*/chrome-mac-arm64/*.app/Contents/MacOS/* 2>/dev/null | sort -V | tail -1)
  [ -n "$c" ] && { echo "$c"; return; }
  c=$(ls -d "$HOME/.cache/ms-playwright"/chromium-*/chrome-linux/chrome 2>/dev/null | sort -V | tail -1)
  [ -n "$c" ] && { echo "$c"; return; }
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "$(command -v chromium || true)" "$(command -v google-chrome || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && { echo "$c"; return; }
  done
  echo ""; return
}

CHROME=$(find_chrome)
if [ -z "$CHROME" ]; then
  echo "ERROR: no Chromium found (Playwright cache or installed Chrome)." >&2
  echo "Install one with: npx -y playwright install chromium" >&2
  exit 1
fi

ABS_IN=$(cd "$(dirname "$IN")" && pwd)/$(basename "$IN")
"$CHROME" --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$ABS_IN"
echo "rendered: $OUT"

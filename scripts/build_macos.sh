#!/usr/bin/env bash
# Build GlowDL.app + DMG on macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

echo "==> 1/5 准备虚拟环境"
if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q -U pip
python -m pip install -q -r requirements.txt
python -m pip install -q "pyinstaller>=6.0"

echo "==> 2/5 生成图标"
python scripts/make_icons.py

echo "==> 3/5 打包（PyInstaller one-dir）"
rm -rf build dist
python -m PyInstaller --noconfirm --clean scripts/glowdl.spec

echo "==> 4/5 临时签名（ad-hoc，未公证）"
if [ -d "dist/GlowDL.app" ]; then
  codesign --deep --force --sign - "dist/GlowDL.app" >/dev/null 2>&1 || true
fi

echo "==> 5/5 生成 DMG"
if [ -d "dist/GlowDL.app" ]; then
  VERSION="$(python -c 'from app import __version__; print(__version__)')"
  DMG="dist/GlowDL-${VERSION}-macOS.dmg"
  rm -f "$DMG"
  hdiutil create -volname "GlowDL" -srcfolder "dist/GlowDL.app" -ov -format UDZO "$DMG" >/dev/null
  echo "完成：$DMG"
else
  echo "未找到 dist/GlowDL.app，请检查 PyInstaller 输出" >&2
  exit 1
fi

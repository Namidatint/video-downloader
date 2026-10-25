"""Generate platform icon assets (PNG / ICNS / ICO) from the vector app icon.

Usage: python scripts/make_icons.py
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.icons import app_pixmap  # noqa: E402

RESOURCES = ROOT / "app" / "resources"


def write_pngs() -> dict[int, Path]:
    RESOURCES.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}
    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        path = RESOURCES / f"icon-{size}.png"
        app_pixmap(size).save(str(path), "PNG")
        out[size] = path
    app_pixmap(512).save(str(RESOURCES / "icon.png"), "PNG")
    return out


def write_ico(sizes: dict[int, Path]) -> Path:
    """Assemble a Windows .ico from PNG frames (PNG-in-ICO is supported by Vista+)."""
    wanted = [16, 32, 48, 64, 128, 256]
    frames = [(s, sizes[s].read_bytes()) for s in wanted]
    header = struct.pack("<HHH", 0, 1, len(frames))
    directory = b""
    offset = 6 + 16 * len(frames)
    payload = b""
    for size, data in frames:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32,
                                 len(data), offset + len(payload))
        payload += data
    ico = RESOURCES / "icon.ico"
    ico.write_bytes(header + directory + payload)
    return ico


def write_icns(sizes: dict[int, Path]) -> Path | None:
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        return None
    iconset = RESOURCES / "VideoDownloader.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()
    mapping = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for name, size in mapping.items():
        shutil.copyfile(sizes[size], iconset / name)
    icns = RESOURCES / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    shutil.rmtree(iconset, ignore_errors=True)
    return icns


def main() -> None:
    app = QApplication([])  # noqa: F841 - required for QPixmap
    sizes = write_pngs()
    ico = write_ico(sizes)
    icns = write_icns(sizes)
    print(f"PNG frames : {len(sizes)} -> {RESOURCES}")
    print(f"Windows ico: {ico} ({ico.stat().st_size} bytes)")
    if icns:
        print(f"macOS icns : {icns} ({icns.stat().st_size} bytes)")
    else:
        print("macOS icns : skipped (iconutil only on macOS)")
    # Drop the intermediate frames, they are only used to build ico/icns.
    for size, path in sizes.items():
        if size not in (256, 512):
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

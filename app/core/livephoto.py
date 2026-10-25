"""Live Photo / Motion Photo packaging.

- iPhone: a JPEG with Apple ContentIdentifier MakerNote + a MOV with the same
  QuickTime key (plus StillImageTime). Photos pairs them on import.
- Android: one JPEG with Google/Samsung Motion Photo metadata and the MP4
  embedded in a Samsung trailer. Google Photos, Gallery and Samsung Gallery
  recognize this single file.
"""

from __future__ import annotations

import io
import struct
import zipfile
import subprocess
import uuid
from pathlib import Path

from app.core.ffmpeg_tools import find_ffmpeg


class LivePhotoError(Exception):
    """Live Photo conversion failed; the message is user-facing."""


def _ffmpeg() -> str:
    status = find_ffmpeg()
    if not status.available:
        raise LivePhotoError("缺少音视频组件，无法生成实况照片。")
    return status.path


def _run(args: list[str]) -> None:
    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=180)
    except Exception as exc:  # noqa: BLE001
        raise LivePhotoError(f"实况转换失败：{exc}") from exc


def still_to_jpeg(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(source), "-frames:v", "1", "-q:v", "2", str(target)])
    if not target.is_file() or target.stat().st_size < 100:
        raise LivePhotoError("静态图转换失败。")
    return target


def _exif_with_makernote(identifier: str) -> bytes:
    import piexif

    exif = {
        "0th": {piexif.ImageIFD.Make: b"Apple",
                piexif.ImageIFD.Orientation: 1},
        "Exif": {piexif.ExifIFD.MakerNote: _apple_makernote(identifier)},
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    return piexif.dump(exif)


def still_to_heic(source: Path, target: Path, identifier: str) -> Path:
    from PIL import Image
    from pillow_heif import register_heif_opener

    register_heif_opener()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = Image.open(source)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(target, "HEIF", quality=92, exif=_exif_with_makernote(identifier))
    except Exception as exc:  # noqa: BLE001
        raise LivePhotoError(f"HEIC 静态图生成失败：{exc}") from exc
    return target


def _local_entries(data: bytes) -> list[tuple[str, int, int]]:
    entries: list[tuple[str, int, int]] = []
    offset = 0
    while offset + 30 <= len(data) and data[offset:offset + 4] == b"PK\x03\x04":
        size = int.from_bytes(data[offset + 18:offset + 22], "little")
        name_len = int.from_bytes(data[offset + 26:offset + 28], "little")
        extra_len = int.from_bytes(data[offset + 28:offset + 30], "little")
        name = data[offset + 30:offset + 30 + name_len].decode("utf-8", "replace")
        data_offset = offset + 30 + name_len + extra_len
        entries.append((name, data_offset, size))
        offset = data_offset + size
    return entries


def write_livp(still_heic: Path, movie: Path, target: Path) -> Path:
    """Build an Apple-compatible .livp ZIP (single file AirDrop/import)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(still_heic, arcname=still_heic.name)
        archive.write(movie, arcname=movie.name)
    data = bytearray(buffer.getvalue())
    entries = _local_entries(bytes(data))
    heic = next((entry for entry in entries if entry[0].lower().endswith((".heic", ".heif"))), None)
    mov = next((entry for entry in entries if entry[0].lower().endswith(".mov")), None)
    if heic is None or mov is None:
        raise LivePhotoError("实况包缺少 HEIC/MOV 文件。")
    comment = "".join((
        "0002", f"{heic[1]:08X}", f"{heic[2]:08X}",
        "0003", f"{mov[1]:08X}", f"{mov[2]:08X}", "313030304C495650",
    )).encode("ascii")
    eocd = bytes(data).rfind(b"PK\x05\x06")
    if eocd < 0:
        raise LivePhotoError("实况包 ZIP 结构异常。")
    data = data[:eocd + 22]
    data[eocd + 20:eocd + 22] = len(comment).to_bytes(2, "little")
    data += comment
    target.write_bytes(data)
    return target


def _apple_makernote(identifier: str) -> bytes:
    """Apple MakerNote carrying tag 0x0011 (ContentIdentifier)."""
    value = identifier.encode("ascii") + b"\x00"
    header = b"Apple iOS\x00" + b"\x00\x01" + b"MM"
    data_offset = len(header) + 2 + 12 + 4
    ifd = struct.pack(">H", 1)
    ifd += struct.pack(">HHII", 0x0011, 2, len(value), data_offset)
    ifd += struct.pack(">I", 0)
    return header + ifd + value


def _write_apple_still(source: Path, target: Path, identifier: str) -> Path:
    import piexif

    still_to_jpeg(source, target)
    try:
        exif = piexif.load(str(target))
    except Exception:
        exif = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif.setdefault("Exif", {})[piexif.ExifIFD.MakerNote] = _apple_makernote(identifier)
    exif.setdefault("0th", {})[piexif.ImageIFD.Make] = b"Apple"
    exif["0th"][piexif.ImageIFD.Orientation] = 1
    try:
        piexif.insert(piexif.dump(exif), str(target))
    except Exception as exc:  # noqa: BLE001
        raise LivePhotoError(f"写入实况标识失败：{exc}") from exc
    return target


def _write_apple_movie(source: Path, target: Path, identifier: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(source), "-c", "copy", "-f", "mov",
          "-movflags", "use_metadata_tags",
          "-metadata", f"com.apple.quicktime.content.identifier={identifier}",
          "-metadata", "com.apple.quicktime.still-image-time=0",
          str(target)])
    if not target.is_file() or target.stat().st_size < 100:
        raise LivePhotoError("动态视频转换失败。")
    return target


def _samsung_trailer(video: bytes) -> tuple[bytes, int]:
    """Samsung Motion Photo trailer; returns (bytes, offset to video start)."""
    marker = b"\x00\x00\x30\x0A"
    trailer = bytearray()
    tags: list[tuple[int, bytes]] = []

    tags.append((len(trailer), marker))
    trailer += marker + struct.pack("<I", 16) + b"MotionPhoto_Data"
    video_offset = len(trailer)
    trailer += video

    tags.append((len(trailer), b""))
    trailer += b"SEFH" + struct.pack("<I", 106) + struct.pack("<I", 1)
    sef_offset = tags[-1][0]
    for index in range(len(tags) - 1):
        negative_offset = sef_offset - tags[index][0]
        length = tags[index + 1][0] - tags[index][0]
        trailer += tags[index][1] + struct.pack("<I", negative_offset) + struct.pack("<I", length)
    trailer += struct.pack("<I", len(trailer) - sef_offset) + b"SEFT"
    return bytes(trailer), len(trailer) - video_offset


def _xmp(negative_offset: int) -> bytes:
    return f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:GCamera="http://ns.google.com/photos/1.0/camera/">
   <GCamera:MicroVideo>1</GCamera:MicroVideo>
   <GCamera:MicroVideoOffset>{negative_offset}</GCamera:MicroVideoOffset>
   <GCamera:MicroVideoPresentationTimestampUs>-1</GCamera:MicroVideoPresentationTimestampUs>
   <GCamera:MicroVideoVersion>1</GCamera:MicroVideoVersion>
   <GCamera:MotionPhoto>1</GCamera:MotionPhoto>
   <GCamera:MotionPhotoVersion>1</GCamera:MotionPhotoVersion>
   <GCamera:MotionPhotoPresentationTimestampUs>-1</GCamera:MotionPhotoPresentationTimestampUs>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''.encode("utf-8")


def _strip_xmp(jpeg: bytes) -> bytes:
    """Remove existing XMP APP1 segments so we can insert one canonical packet."""
    out = bytearray(jpeg[:2])
    pos = 2
    while pos + 4 <= len(jpeg):
        if jpeg[pos] != 0xFF:
            break
        marker = jpeg[pos + 1]
        if marker == 0xDA:  # start of scan: keep the rest untouched
            out += jpeg[pos:]
            return bytes(out)
        length = int.from_bytes(jpeg[pos + 2:pos + 4], "big")
        end = pos + 2 + length
        payload = jpeg[pos + 4:end]
        is_xmp = marker == 0xE1 and payload.startswith(b"http://ns.adobe.com/xap/1.0/")
        if not is_xmp:
            out += jpeg[pos:end]
        pos = end
    return bytes(out)


def write_android_motion(still_jpeg: Path, motion: Path, target: Path) -> Path:
    jpeg = still_jpeg.read_bytes()
    video = motion.read_bytes()
    # Keep only the JPEG part; a fresh XMP packet is inserted after SOI.
    trailer, negative_offset = _samsung_trailer(video)
    data = _strip_xmp(jpeg) + trailer
    payload = b"http://ns.adobe.com/xap/1.0/\x00" + _xmp(negative_offset)
    if len(payload) + 2 > 0xFFFF:
        raise LivePhotoError("实况元数据过大。")
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data[:2] + segment + data[2:])
    return target


def build_live_pack(still: Path, motion: Path, out_dir: Path, base: str) -> list[Path]:
    """Build iPhone pair + Android single-file Motion Photo under out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    iphone = out_dir / "iPhone"
    android = out_dir / "Android"
    iphone.mkdir(exist_ok=True)
    android.mkdir(exist_ok=True)

    identifier = str(uuid.uuid4()).upper()
    safe = "".join(ch for ch in base if ch.isalnum() or ch in "-_") or "Live"
    apple_still = _write_apple_still(still, iphone / f"IMG_{safe}.JPG", identifier)
    apple_movie = _write_apple_movie(motion, iphone / f"IMG_{safe}.MOV", identifier)
    apple_heic = still_to_heic(still, iphone / f"IMG_{safe}.HEIC", identifier)
    livp = write_livp(apple_heic, apple_movie, out_dir / "LivePhoto.livp")

    android_jpeg = android / f"MV_{safe}.jpg"
    still_to_jpeg(still, android_jpeg)
    write_android_motion(android_jpeg, motion, android_jpeg)

    note = out_dir / "说明.txt"
    note.write_text(
        "iPhone：优先把 LivePhoto.livp AirDrop 到 iPhone，用「文件」打开并存储到照片；"
        "也可把 iPhone 文件夹里的 JPG/HEIC + MOV 一起导入「照片」。\n"
        "Android：把 Android 文件夹里的 MV_*.jpg 传到手机，"
        "用 Google 相册 / 三星相册打开即为动态照片。\n",
        encoding="utf-8",
    )
    return [livp, apple_still, apple_heic, apple_movie, android_jpeg, note]

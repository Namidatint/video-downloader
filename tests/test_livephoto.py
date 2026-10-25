"""Live Photo container helpers (no browser / no network)."""

from __future__ import annotations

import struct

from app.core import livephoto


def test_apple_makernote_contains_identifier():
    data = livephoto._apple_makernote("1234-ABCD")
    assert data.startswith(b"Apple iOS\x00")
    assert b"1234-ABCD" in data
    # one IFD entry, tag 0x0011
    header_len = len(b"Apple iOS\x00") + 2 + 2
    assert struct.unpack(">H", data[header_len:header_len + 2])[0] == 1
    assert struct.unpack(">H", data[header_len + 2:header_len + 4])[0] == 0x0011


def test_samsung_trailer_shape():
    trailer, negative_offset = livephoto._samsung_trailer(b"VIDEO")
    assert b"MotionPhoto_Data" in trailer
    assert trailer.startswith(b"\x00\x00\x30\x0A")
    assert trailer.endswith(b"SEFT")
    assert negative_offset > 0
    assert trailer[-negative_offset:].startswith(b"VIDEO")


def test_google_xmp_has_required_tags():
    xmp = livephoto._xmp(123456)
    assert b"GCamera:MicroVideo>1" in xmp
    assert b"MicroVideoOffset>123456" in xmp
    assert b"MotionPhoto>1" in xmp

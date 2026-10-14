"""Face write payloads and image handling for the camerahub face API.

Field names and the set/del/verify operations are recovered from the Tapo APK
(``libtapocameranetwork`` face models: AddFaceRequest, SetFaceInfoRequest,
FaceInfoOperation, FaceCoverInfo). Every builder here is pure so the panel
payloads/commands can be unit-checked without a camera or Home Assistant.
"""

from __future__ import annotations

import base64
import binascii
import io
from typing import Any

try:
    from .face import FACE_TAGS, _image_type
except ImportError:  # imported as a top-level module by the test harness
    from face import FACE_TAGS, _image_type

MAX_FACE_NAME_BYTES = 32
DEFAULT_PIC_FORMAT = 2
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
JPEG_QUALITY = 50

_OPERATE_SET = "set"
_OPERATE_DEL = "del"
_OPERATE_VERIFY = "verify"


def normalize_name(value: Any) -> str:
    """A face name is trimmed, non-blank and at most 32 UTF-8 bytes (APK rule)."""
    if not isinstance(value, str):
        raise TypeError("Tên khuôn mặt phải là chuỗi")
    name = value.strip()
    if not name:
        raise ValueError("Hãy nhập tên khuôn mặt")
    if len(name.encode("utf-8")) > MAX_FACE_NAME_BYTES:
        raise ValueError(f"Tên tối đa {MAX_FACE_NAME_BYTES} byte")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("Tên chứa ký tự không hợp lệ")
    return name


def normalize_tag(value: Any) -> str:
    if value not in FACE_TAGS:
        raise ValueError("Nhóm khuôn mặt không hợp lệ")
    return str(value)


def face_identifier(value: Any) -> int:
    """A numeric catalog id; never invent one for a write target."""
    if isinstance(value, bool):
        raise TypeError("Face ID không hợp lệ")
    if isinstance(value, int):
        identifier = value
    elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
        identifier = int(value.strip())
    else:
        raise ValueError("Face ID không hợp lệ")
    if identifier < 0:
        raise ValueError("Face ID không hợp lệ")
    return identifier


def set_face_payload(face_id: Any, *, name: str | None = None, tag: str | None = None) -> dict:
    """Rename (cover.name) or re-tag (cover.tag); at least one field required."""
    identifier = face_identifier(face_id)
    cover: dict[str, Any] = {"face_id": identifier}
    if name is not None:
        cover["name"] = normalize_name(name)
    if tag is not None:
        cover["tag"] = normalize_tag(tag)
    if len(cover) == 1:
        raise ValueError("Cần tên mới hoặc nhóm mới")
    return {"face_detection": {"set_face_info": {"commands": [
        {"operate": _OPERATE_SET, "ori_face_id": identifier, "cover": cover}
    ]}}}


def delete_face_payload(face_id: Any) -> dict:
    identifier = face_identifier(face_id)
    return {"face_detection": {"set_face_info": {"commands": [
        {"operate": _OPERATE_DEL, "ori_face_id": identifier, "cover": {}}
    ]}}}


def verify_face_payload(face_id: Any) -> dict:
    identifier = face_identifier(face_id)
    return {"face_detection": {"set_face_info": {"commands": [
        {"operate": _OPERATE_VERIFY, "ori_face_id": identifier, "cover": {}}
    ]}}}


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    index, size = 2, len(data)
    while index + 9 < size:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment = int.from_bytes(data[index + 2:index + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            return width, height
        index += 2 + segment
    return None


def _dimensions(data: bytes) -> tuple[int, int]:
    return _png_size(data) or _jpeg_size(data) or (0, 0)


def _to_jpeg(data: bytes) -> bytes:
    """Normalize any accepted image to JPEG; needs Pillow only for non-JPEG."""
    if _image_type(data) == "image/jpeg":
        return data
    try:
        from PIL import Image
    except ImportError:
        raise ValueError("Chỉ nhận ảnh JPEG (không có Pillow để đổi định dạng)") from None
    try:
        with Image.open(io.BytesIO(data)) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY)
            return buffer.getvalue()
    except (OSError, ValueError):
        raise ValueError("Ảnh không hợp lệ") from None


def extract_image_bytes(value: Any) -> bytes:
    """Accept a browser data URL or a plain base64 payload, bounded in size."""
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
    elif isinstance(value, str):
        text = value.strip()
        if text.startswith("data:"):
            _, separator, text = text.partition(",")
            if not separator:
                raise ValueError("Ảnh không hợp lệ")
        compact = "".join(text.split())
        if len(compact) > 4 * ((MAX_UPLOAD_BYTES + 2) // 3) + 256:
            raise ValueError("Ảnh quá lớn")
        try:
            data = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Ảnh không hợp lệ") from None
    else:
        raise TypeError("Thiếu ảnh")
    if not data or len(data) > MAX_UPLOAD_BYTES or _image_type(data) is None:
        raise ValueError("Ảnh không hợp lệ hoặc quá lớn")
    return data


def encode_face_image(value: Any) -> dict:
    """Return the base64 JPEG plus byte size and pixel dimensions for add_face."""
    jpeg = _to_jpeg(extract_image_bytes(value))
    width, height = _dimensions(jpeg)
    return {
        "face_info": base64.b64encode(jpeg).decode("ascii"),
        "face_size": len(jpeg),
        "width": width,
        "height": height,
    }


def add_face_payload(name: Any, tag: Any, image: dict, *, face_id: int = 0) -> dict:
    """Build doFaceInfoAdd from an encoded image (see encode_face_image)."""
    identifier = face_identifier(face_id)
    width = int(image.get("width") or 0)
    height = int(image.get("height") or 0)
    if width < 1 or height < 1:
        raise ValueError("Không đọc được kích thước ảnh")
    body: dict[str, Any] = {
        "name": normalize_name(name),
        "tag": normalize_tag(tag),
        "face_id": identifier,
        "width": width,
        "height": height,
        "face_info": image["face_info"],
        "padding_info": {"x_min": 0, "x_max": width, "y_min": 0, "y_max": height},
    }
    if isinstance(image.get("face_size"), int) and image["face_size"] > 0:
        body["face_size"] = image["face_size"]
    return {"face_detection": {"action_face_info_add": body}}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_set_face_payload(params: Any) -> bool:
    """Shape check so only set/del/verify commands reach the camera."""
    try:
        commands = params["face_detection"]["set_face_info"]["commands"]
    except (KeyError, TypeError):
        return False
    if not isinstance(commands, list) or len(commands) != 1 or not isinstance(commands[0], dict):
        return False
    command = commands[0]
    operate, cover = command.get("operate"), command.get("cover")
    if set(command) != {"operate", "ori_face_id", "cover"} or not _is_int(command.get("ori_face_id")):
        return False
    try:
        identifier = face_identifier(command["ori_face_id"])
    except (TypeError, ValueError):
        return False
    if operate == _OPERATE_SET:
        if not isinstance(cover, dict) or set(cover) - {"face_id", "name", "tag"} or "face_id" not in cover:
            return False
        if not _is_int(cover["face_id"]) or face_identifier(cover["face_id"]) != identifier:
            return False
        if "name" in cover and normalize_name(cover["name"]) != cover["name"]:
            return False
        if "tag" in cover and normalize_tag(cover["tag"]) != cover["tag"]:
            return False
        return "name" in cover or "tag" in cover
    if operate in (_OPERATE_DEL, _OPERATE_VERIFY):
        return cover == {}
    return False


def is_add_face_payload(params: Any) -> bool:
    """Shape check mirroring AddFaceRequest so only a bounded add passes."""
    try:
        body = params["face_detection"]["action_face_info_add"]
    except (KeyError, TypeError):
        return False
    if not isinstance(body, dict):
        return False
    if set(body) - {"name", "tag", "face_id", "width", "height", "face_info", "padding_info", "face_size"}:
        return False
    if {"name", "tag", "face_id", "width", "height", "face_info", "padding_info"} - set(body):
        return False
    if not _is_int(body["face_id"]) or body["face_id"] < 0:
        return False
    if not _is_int(body["width"]) or not _is_int(body["height"]) or body["width"] < 1 or body["height"] < 1:
        return False
    if not isinstance(body["face_info"], str) or not body["face_info"] or len(body["face_info"]) > 8_000_000:
        return False
    padding = body["padding_info"]
    if not isinstance(padding, dict) or set(padding) != {"x_min", "x_max", "y_min", "y_max"}:
        return False
    if not all(_is_int(value) for value in padding.values()):
        return False
    if "face_size" in body and not _is_int(body["face_size"]):
        return False
    try:
        normalize_name(body["name"])
        normalize_tag(body["tag"])
    except (TypeError, ValueError):
        return False
    return True

"""Secure attachment handling.

* Files are streamed to a private temp directory with an early size cut-off.
* The real content type is detected from magic bytes; images are fully decoded
  with Pillow (also guards against decompression bombs). Extensions are ignored.
* Stored names are random UUIDs under a private root that is never served
  directly; downloads go through an authorised API endpoint.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.services.errors import ValidationFailed
from app.services.form_engine import FileRules

Image.MAX_IMAGE_PIXELS = 120_000_000  # ~120 MP; larger images are rejected

_CHUNK = 1024 * 256
_MIME_LABELS = {"image/jpeg": "JPG/JPEG", "image/png": "PNG", "application/pdf": "PDF"}
_EXT = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}


@dataclass
class ValidatedFile:
    temp_path: Path
    original_filename: str
    mime_type: str
    size: int
    sha256: str
    kind: str
    width: int | None = None
    height: int | None = None

    @property
    def ext(self) -> str:
        return _EXT[self.mime_type]


def storage_root() -> Path:
    root = Path(get_settings().storage_dir).resolve()
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    return root


def safe_display_name(name: str | None) -> str:
    name = (name or "file").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f\"<>|*?:]", "", name).strip() or "file"
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 190] + "." + ext) if dot and len(ext) <= 8 else name[:200]
    return name


def sniff_mime(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _inspect_image(path: Path, expected_mime: str) -> tuple[int, int]:
    expected_format = {"image/jpeg": "JPEG", "image/png": "PNG"}[expected_mime]
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as im:
            if im.format != expected_format:
                raise ValueError("format mismatch")
            im.verify()
        with Image.open(path) as im:  # verify() invalidates the image; reopen to read size / decode
            im.load()
            return im.size


def _receive_one(upload: UploadFile, rules: FileRules, tmp_dir: Path) -> ValidatedFile:
    name = safe_display_name(upload.filename)
    max_bytes = rules.max_size_mb * 1024 * 1024
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = upload.file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValidationFailed(
                        f"ไฟล์ {name} มีขนาดเกิน {rules.max_size_mb} MB",
                        fields={"attachments": f"ไฟล์ {name} มีขนาดเกิน {rules.max_size_mb} MB"},
                    )
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise ValidationFailed(f"ไฟล์ {name} ว่างเปล่า", fields={"attachments": f"ไฟล์ {name} ว่างเปล่า"})
        mime = sniff_mime(head)
        if mime is None or mime not in rules.accept:
            allowed = ", ".join(_MIME_LABELS[m] for m in rules.accept)
            msg = f"ไฟล์ {name} ไม่ใช่ประเภทที่รองรับ (รองรับ {allowed})"
            raise ValidationFailed(msg, fields={"attachments": msg})
        width = height = None
        kind = "DOCUMENT"
        if mime.startswith("image/"):
            kind = "IMAGE"
            try:
                width, height = _inspect_image(tmp_path, mime)
            except (UnidentifiedImageError, ValueError, OSError, SyntaxError, Image.DecompressionBombError,
                    Image.DecompressionBombWarning):
                msg = f"ไฟล์รูปภาพ {name} เสียหายหรือไม่สามารถเปิดได้"
                raise ValidationFailed(msg, fields={"attachments": msg}) from None
        return ValidatedFile(
            temp_path=tmp_path, original_filename=name, mime_type=mime, size=size,
            sha256=digest.hexdigest(), kind=kind, width=width, height=height,
        )
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def receive_uploads(uploads: list[UploadFile], rules: FileRules, existing_count: int = 0) -> list[ValidatedFile]:
    """Validate all uploads or none. Duplicate contents within one request are dropped."""
    uploads = [u for u in uploads if u is not None and (u.filename or u.size)]
    if not uploads:
        return []
    if rules.max_files <= 0:
        raise ValidationFailed("แบบฟอร์มนี้ไม่รองรับไฟล์แนบ", fields={"attachments": "ไม่รองรับไฟล์แนบ"})
    if len(uploads) + existing_count > rules.max_files:
        msg = f"แนบไฟล์ได้สูงสุด {rules.max_files} ไฟล์ต่อ Ticket"
        raise ValidationFailed(msg, fields={"attachments": msg}, code="TOO_MANY_FILES")
    tmp_dir = storage_root() / "tmp"
    received: list[ValidatedFile] = []
    try:
        seen: set[str] = set()
        for up in uploads:
            vf = _receive_one(up, rules, tmp_dir)
            if vf.sha256 in seen:
                vf.temp_path.unlink(missing_ok=True)
                continue
            seen.add(vf.sha256)
            received.append(vf)
    except BaseException:
        discard(received)
        raise
    return received


def _ticket_dir(ticket_id: int) -> str:
    return f"tickets/{ticket_id // 1000:05d}/{ticket_id}"


def persist(vf: ValidatedFile, ticket_id: int) -> str:
    """Move a validated temp file to its final private location; returns the relative path."""
    rel = f"{_ticket_dir(ticket_id)}/{uuid.uuid4().hex}.{vf.ext}"
    dest = storage_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(vf.temp_path, dest)
    os.chmod(dest, 0o640)
    return rel


def discard(files: list[ValidatedFile]) -> None:
    for vf in files:
        vf.temp_path.unlink(missing_ok=True)


def remove_stored(paths: list[str]) -> None:
    for rel in paths:
        try:
            resolve_stored(rel).unlink(missing_ok=True)
        except ValueError:
            pass


def resolve_stored(rel: str) -> Path:
    root = storage_root()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise ValueError("path escapes storage root")
    return path


def remove_ticket_dir(ticket_id: int) -> None:
    shutil.rmtree(storage_root() / _ticket_dir(ticket_id), ignore_errors=True)

"""CSV helpers: Excel-friendly UTF-8 (with BOM) and protection against formula injection."""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.responses import Response

from app.config import get_settings

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo(get_settings().timezone)).strftime("%Y-%m-%d %H:%M")
    text = str(value)
    if text.startswith(_DANGEROUS):
        text = "'" + text  # neutralise spreadsheet formulas
    return text


def csv_response(filename: str, header: list[str], rows: Iterable[Iterable[object]]) -> Response:
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([cell(v) for v in r])
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

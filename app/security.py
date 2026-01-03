from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import quote
from hashlib import sha256
from base64 import b64decode, b64encode
import os

SLUG_RE = re.compile(r"[^a-z0-9\-]+")



def slugify(text: str) -> str:
    t = (text or "").strip().lower().replace(" ", "-")
    t = SLUG_RE.sub("", t)
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return t or "item"

def safe_limit(s: str, n: int) -> str:
    return (s or "")[:n]

def build_url_encode_table() -> Dict[int, str]:
    tbl: Dict[int, str] = {}
    for i in list(range(32, 127)) + list(range(161, 256)):
        tbl[i] = quote(chr(i), safe="")
    return tbl

_URL_ENCODE_TABLE: Optional[Dict[int, str]] = None

def get_url_encode_table() -> Dict[int, str]:
    global _URL_ENCODE_TABLE
    if _URL_ENCODE_TABLE is None:
        _URL_ENCODE_TABLE = build_url_encode_table()
    return _URL_ENCODE_TABLE

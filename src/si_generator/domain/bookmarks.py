from __future__ import annotations

import hashlib
import re


def bookmark_name_for_block_id(block_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", block_id)
    safe = re.sub(r"_+", "_", safe).strip("_") or "block"
    if not safe[0].isalpha():
        safe = "b_" + safe
    digest = hashlib.sha1(block_id.encode("utf-8")).hexdigest()[:8]
    prefix = "asig_"
    max_safe_len = 40 - len(prefix) - len(digest) - 1
    return f"{prefix}{safe[:max_safe_len]}_{digest}"

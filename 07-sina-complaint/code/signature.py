"""Signature generation for the search endpoint."""

import hashlib
import random
import string
import time

SEARCH_SIGNATURE_SALT = "$d6eb7ff91ee257475%"


def build_search_params(keywords: str, page: int, page_size: int = 10) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    nonce = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
    values = [SEARCH_SIGNATURE_SALT, keywords, str(page_size), str(page), timestamp, nonce]
    signature = hashlib.sha256("".join(sorted(values)).encode("utf-8")).hexdigest()
    return {
        "ts": timestamp,
        "rs": nonce,
        "signature": signature,
        "keywords": keywords,
        "page_size": str(page_size),
        "page": str(page),
    }

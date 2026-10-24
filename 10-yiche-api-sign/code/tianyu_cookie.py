"""Build a Tencent Tianyu challenge cookie for authorized Yiche requests."""

from __future__ import annotations

import base64
import re

RC4_KEY = "tg09It3*9h"
CHALLENGE_PATTERN = re.compile(
    r"var _xvasu = (\d+);.*?var _xvpts = ([0-9.]+);",
    re.DOTALL,
)


def rc4(key: str, value: str) -> bytes:
    key_bytes = key.encode("latin1")
    value_bytes = value.encode("latin1")
    if not key_bytes:
        raise ValueError("RC4 key must not be empty")

    state = list(range(256))
    offset = 0
    for index in range(256):
        offset = (offset + state[index] + key_bytes[index % len(key_bytes)]) % 256
        state[index], state[offset] = state[offset], state[index]

    output = bytearray()
    index = 0
    offset = 0
    for byte in value_bytes:
        index = (index + 1) % 256
        offset = (offset + state[index]) % 256
        state[index], state[offset] = state[offset], state[index]
        output.append(byte ^ state[(state[index] + state[offset]) % 256])
    return bytes(output)


def build_tianyu_cookie(response_text: str) -> dict[str, str] | None:
    match = CHALLENGE_PATTERN.search(response_text)
    if not match:
        return None

    xvasu, xvpts = match.groups()
    payload = f"{xvpts}:{xvasu}"
    value = base64.b64encode(rc4(RC4_KEY, payload)).decode("ascii")
    return {
        "name": f"tws2_{xvasu}",
        "value": value,
        "domain": ".yiche.com",
        "path": "/",
    }


"""Build the signed parameter-detail request used by the vehicle API."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from urllib.parse import urlencode

SIGN_SUFFIX = "19DDD1FBDFF065D3A4DA777D2D7A81EC"
ENDPOINT = "https://mhapi.yiche.com/hcar/h_car/api/v1/param/get_param_details"


def build_signed_request(serial_id: str, *, city_id: str = "501") -> tuple[str, dict[str, str]]:
    timestamp = str(int(time.time() * 1000))
    params = {"cityId": city_id, "serialId": str(serial_id)}
    compact_params = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
    cid = "508"
    signature_source = f"cid={cid}&param={compact_params}{SIGN_SUFFIX}{timestamp}"
    signature = hashlib.md5(signature_source.encode("utf-8")).hexdigest()
    url = f"{ENDPOINT}?{urlencode({'cid': cid, 'param': compact_params})}"
    headers = {
        "x-sign": signature,
        "x-timestamp": timestamp,
        "x-user-guid": str(uuid.uuid4()),
    }
    return url, headers

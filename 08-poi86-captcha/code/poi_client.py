"""POI86 captcha-backed GeoJSON client."""

from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Any

import requests

BASE_URL = "https://www.poi86.com"
OCR_URL = os.environ.get("POI_OCR_URL", "")
USER_AGENT = os.environ.get(
    "POI_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36",
)


def _ocr(image: bytes) -> str:
    if not OCR_URL:
        raise RuntimeError("Set POI_OCR_URL to an authorized OCR service endpoint")
    response = requests.post(
        OCR_URL,
        data={"old": "true", "img_data": base64.b64encode(image).decode("ascii")},
        timeout=20,
    )
    response.raise_for_status()
    result = response.json().get("ret")
    if not result:
        raise ValueError("OCR response did not contain a captcha result")
    return str(result)


def _geojson_from_zip(body: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        name = next((item for item in archive.namelist() if re.fullmatch(r"\d+\.geojson", item)), None)
        if name is None:
            raise ValueError("Response archive does not contain a numeric GeoJSON file")
        return archive.read(name).decode("utf-8")


def fetch_geojson(identifier: str, *, is_street: bool, session: requests.Session | None = None, attempts: int = 8) -> str:
    """Fetch one area/street GeoJSON; OCR endpoint must be configured by caller."""
    client = session or requests.Session()
    client.headers.update({"User-Agent": USER_AGENT, "Referer": f"{BASE_URL}/"})
    last_error: Exception | None = None
    try:
        for _ in range(attempts):
            try:
                captcha = client.get(f"{BASE_URL}/Captcha", timeout=20)
                captcha.raise_for_status()
                code = _ocr(captcha.content)
                endpoint = "/GeoJson/Street" if is_street else "/GeoJson/Area"
                data: dict[str, Any] = {
                    "type": "",
                    "Captcha": code,
                    "streetid" if is_street else "adcode": identifier,
                }
                if not is_street:
                    data["isSub"] = "true"
                response = client.post(f"{BASE_URL}{endpoint}", data=data, timeout=30)
                response.raise_for_status()
                if "验证码错误" in response.content.decode("utf-8", errors="ignore"):
                    raise ValueError("Captcha rejected")
                return _geojson_from_zip(response.content)
            except (requests.RequestException, ValueError, zipfile.BadZipFile) as exc:
                last_error = exc
        raise RuntimeError(f"GeoJSON request failed after {attempts} attempts") from last_error
    finally:
        if session is None:
            client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("identifier")
    parser.add_argument("--street", action="store_true")
    args = parser.parse_args()
    print(fetch_geojson(args.identifier, is_street=args.street))



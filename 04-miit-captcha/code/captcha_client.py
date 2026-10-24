"""Standalone OCR client for the public enterprise-query endpoints."""

import base64
import re
from urllib.parse import urlencode

import ddddocr
import requests

CAPTCHA_URL = "https://dxzhgl.miit.gov.cn/dxxzsp/corpinfo/getCode"
QUERY_URL = "https://dxzhgl.miit.gov.cn/dxxzsp/corpinfo/getcorpinfo.wf"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"


def query_company(company_name: str, max_attempts: int = 5) -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest"})
    ocr = ddddocr.DdddOcr(show_ad=False)

    for _ in range(max_attempts):
        captcha_response = session.post(CAPTCHA_URL, params={"num": company_name}, timeout=20)
        captcha_response.raise_for_status()
        image_data = captcha_response.json().get("src", "")
        if "," not in image_data:
            continue
        image_bytes = base64.b64decode(image_data.split(",", 1)[1])
        code = ocr.classification(image_bytes).strip().upper()
        if len(code) != 7 or not re.fullmatch(r"[A-Z0-9]{7}", code):
            continue

        response = session.post(
            QUERY_URL,
            params={"pageNum": "1", "pageSize": "10"},
            data={"num": company_name, "type": "xuke", "code": code},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if "listyj" in payload and "验证" not in response.text:
            return payload

    raise RuntimeError("Captcha/query did not succeed within retry limit")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("company_name")
    args = parser.parse_args()
    print(json.dumps(query_company(args.company_name), ensure_ascii=False, indent=2))

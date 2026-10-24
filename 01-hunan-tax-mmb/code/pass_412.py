# -*- coding: utf-8 -*-
"""湖南税务 412 -> JS challenge -> 二次请求 200 验证脚本。"""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
OUTPUT = ROOT / "output"
SOLVER = ROOT / "solve_mmb_cookie.js"

URL = "https://hunan.chinatax.gov.cn/taxpayerstatesearch/20190413003982"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": URL,
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def cookie_header(session: requests.Session) -> str:
    return "; ".join(f"{c.name}={c.value}" for c in session.cookies)


def update_session_cookie_from_header(session: requests.Session, header: str, domain="hunan.chinatax.gov.cn"):
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.lower() in {"path", "expires", "max-age", "domain", "samesite", "secure", "httponly"}:
            continue
        session.cookies.set(k, v, domain=domain, path="/")


def find_script_url(html: str) -> str:
    m = re.search(r'<script[^>]+src=["\']([^"\']+ZYbKRgIknL7izCT\.js)["\']', html, re.I)
    if not m:
        m = re.search(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html, re.I)
    if not m:
        raise RuntimeError("412 页面里没有找到挑战 JS src")
    return urljoin(URL, m.group(1))


def call_node_solver(js_path: Path, page_url: str, ua: str, init_cookie: str) -> dict:
    payload = {
        "jsPath": str(js_path),
        "pageUrl": page_url,
        "userAgent": ua,
        "cookie": init_cookie,
    }
    p = subprocess.run(
        ["node", str(SOLVER)],
        input=json.dumps(payload, ensure_ascii=True),
        text=True,
        capture_output=True,
        timeout=45,
        cwd=str(ROOT),
    )
    if p.returncode != 0:
        raise RuntimeError(f"node solver failed\nSTDOUT={p.stdout}\nSTDERR={p.stderr}")
    data = json.loads(p.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"node solver error: {data}")
    return data


def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    s = requests.Session()

    print("[1] 首次请求，预期 412")
    r1 = s.get(URL, headers=HEADERS, verify=False, timeout=20)
    print("    status:", r1.status_code)
    print("    set-cookie:", r1.headers.get("Set-Cookie"))
    if r1.status_code != 412:
        print("    首包不是 412，仍继续尝试。")

    script_url = find_script_url(r1.text)
    js_path = SOURCE / Path(script_url).name
    print("[2] 下载挑战 JS:", script_url)
    rjs = s.get(script_url, headers={"User-Agent": UA, "Referer": URL}, verify=False, timeout=20)
    rjs.raise_for_status()
    js_path.write_bytes(rjs.content)
    print("    js bytes:", js_path.stat().st_size)

    init_cookie = cookie_header(s)
    print("[3] Node 本地执行挑战 JS，生成 clearance cookie")
    solved = call_node_solver(js_path, URL, UA, init_cookie)
    print("    writes:", solved.get("writes"))
    print("    cookieHeader:", solved.get("cookieHeader"))
    update_session_cookie_from_header(s, solved["cookieHeader"])

    print("[4] 二次请求，预期 200")
    headers2 = dict(HEADERS)
    headers2["Cookie"] = cookie_header(s)
    r2 = s.get(URL, headers=headers2, verify=False, timeout=20)
    print("    status:", r2.status_code)
    print("    final cookies:", cookie_header(s))
    out = OUTPUT / "second_response.html"
    out.write_text(r2.text, encoding=r2.encoding or "utf-8", errors="ignore")
    print("    saved:", out)
    print("    body head:", r2.text[:300].replace("\n", " "))

    if r2.status_code != 200:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


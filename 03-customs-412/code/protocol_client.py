"""HTTP session wrapper around the bundled JavaScript challenge runner."""

import json
import subprocess
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from helpers import Page, UA, apply_cookie_writes

RUNNER = Path(__file__).with_name("run.js")
MAX_CHALLENGE_ROUNDS = 5


class ProtocolClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})

    def close(self):
        self.session.close()

    def get(self, url: str, referer: str = ""):
        response = self.session.get(url, headers={"Referer": referer or url}, timeout=(10, 40))
        for _ in range(MAX_CHALLENGE_ROUNDS):
            if response.status_code != 412:
                break
            page = Page(response.content.decode("utf-8"))
            scripts = []
            for index, script in enumerate(page.scripts):
                if script.get("src"):
                    script_url = urljoin(response.url, script["src"])
                    if urlsplit(script_url).hostname != urlsplit(response.url).hostname:
                        raise ValueError("Challenge script host does not match page host")
                    script_response = self.session.get(script_url, headers={"Referer": response.url}, timeout=(10, 40))
                    script_response.raise_for_status()
                    scripts.append({"code": script_response.text, "filename": f"script_{index}.js", "src": script_url})
                else:
                    scripts.append({"code": script["code"], "filename": f"inline_{index}.js"})
            visible_cookies = requests.cookies.RequestsCookieJar()
            for cookie in self.session.cookies:
                if not cookie.has_nonstandard_attr("HttpOnly"):
                    visible_cookies.set_cookie(cookie)
            request = requests.Request("GET", response.url).prepare()
            payload = {
                "html": response.text,
                "pageUrl": response.url,
                "userAgent": UA,
                "cookie": requests.cookies.get_cookie_header(visible_cookies, request) or "",
                "scripts": scripts,
                "metas": page.metas,
            }
            process = subprocess.run(
                ["node", str(RUNNER)], input=json.dumps(payload), capture_output=True,
                text=True, encoding="utf-8", timeout=40, cwd=RUNNER.parent, check=False,
            )
            result = json.loads(process.stdout)
            if process.returncode or not result.get("ok") or not result.get("writes"):
                raise RuntimeError("Challenge execution failed")
            apply_cookie_writes(self.session, result["writes"], response.url)
            response = self.session.get(url, headers={"Referer": referer or url}, timeout=(10, 40))
        response.raise_for_status()
        return response

"""Generate the time/category parameter used by ICKEY search APIs."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import execjs
import requests
from lxml import html

BASE_URL = "https://www.ickey.cn"
SEARCH_URL = "https://search.ickey.cn/x/c/949bb3095f7584c61275ab55fa45de8e"
DEFAULT_DETAIL_URL = "https://www.ickey.cn/detail/1003001124766549/RTT0361R9FTP.html"
FUNCTION_NAME = "x1f3cdd852bcef773ecae4608e0cd9b82"

ENV_PREFIX = r"""
function getEnvs(names) {
  for (const name of names) {
    try {
      const target = eval(name);
      eval(name + ' = new Proxy(target, {get: (t,p,r) => Reflect.get(t,p,r), set: (t,p,v,r) => Reflect.set(t,p,v,r)})');
    } catch (_) {
      eval(name + ' = {}');
    }
  }
}
var window = global;
var document = global.document || {};
var location = global.location || {};
var navigator = global.navigator || {};
var history = global.history || {};
var screen = global.screen || {};
getEnvs(['window','document','location','navigator','history','screen']);
"""


@dataclass
class IckeySigner:
    session: requests.Session
    context: object
    csrf: str
    font_ident: str

    @classmethod
    def bootstrap(cls, detail_url: str = DEFAULT_DETAIL_URL) -> "IckeySigner":
        session = requests.Session()
        page = session.get(detail_url, timeout=20)
        page.raise_for_status()
        tree = html.fromstring(page.content)
        csrf_values = tree.xpath("//input[@name='_csrf']/@value")
        font_values = re.findall(r"['\"]font_ident['\"]\s*:\s*['\"]([a-f0-9]+)", page.text)
        if not csrf_values or not font_values:
            raise ValueError("Could not initialize CSRF/font parameters from detail page")

        script = session.get(SEARCH_URL, headers={"Referer": detail_url}, timeout=20)
        script.raise_for_status()
        if FUNCTION_NAME not in script.text:
            raise ValueError("Expected signing function was not found in script response")
        source_path = os.path.join(os.path.dirname(__file__), "ickey_challenge.js")
        with open(source_path, encoding="utf-8") as source_file:
            challenge_source = source_file.read()
        context = execjs.compile(ENV_PREFIX + challenge_source + script.text)
        return cls(session, context, csrf_values[0], font_values[0])

    def make_parameter(self, timestamp: str, category_id: str) -> str:
        encoded_category = base64.b64encode(category_id.encode("utf-8")).decode("ascii")
        seed = hashlib.md5((timestamp + encoded_category).encode("utf-8")).hexdigest()
        intermediate = self.context.call(FUNCTION_NAME, seed)
        return self.context.call("hex_md5", timestamp + encoded_category + intermediate)

    def search_params(self, category_id: str, *, page: int = 0, page_size: int = 50) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        return {
            "page": str(page),
            "page_size": str(page_size),
            "cate_id": category_id,
            "p": self.make_parameter(timestamp, category_id),
            "v": timestamp,
            "v_": "_0x107687",
            "_csrf": self.csrf,
            "_": str(int(time.time() * 1000)),
        }

    def close(self) -> None:
        self.session.close()


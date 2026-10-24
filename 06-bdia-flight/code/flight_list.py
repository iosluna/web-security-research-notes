"""Pure-Python client for the bdia session handshake and flight lists.

The page-side implementation uses two AES-128-CBC layers:

1. Encrypt a fixed seed with the fixed key and IV; bytes 4..19 become the
   session key.
2. Generate a 16-character ``etag`` and use it as IV for the session payload.

Ciphertext is standard Base64 with ``/`` replaced by ``_``. ``+`` and ``=``
remain unchanged, matching the JavaScript implementation.

Flight lists arrive as MessagePack WebSocket DOM patches. Date selections are
sent as native mouse events; each direction and day is saved to its own JSON.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import struct
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit
from zoneinfo import ZoneInfo

import requests
from Crypto.Cipher import AES
from websocket import WebSocketBadStatusException, WebSocketTimeoutException, create_connection


BASE_URL = "https://www.bdia.com.cn/1ywuKELSO2ahQuWZ"
SESSIONS_URL = f"{BASE_URL}/api/v1/sessions"
LONG_PROXY_URL = os.environ.get("BDIA_PROXY_API_URL", "")
AES_MODE = AES.MODE_CBC
FIXED_KEY = b"E08247708934F42E"
FIXED_IV = b"0A234C4C639E015D"
KEY_SEED = (
    "kZbArlh63MZUTF3Qyf9mjpoy+Fxf+3CCtsm8og1TDy8eAChQ1ZiRBO59yePYNEUwqTdQsPWmVQguihOonpQw"
)


def get_long_proxy() -> dict[str, str] | None:
    response = requests.get(LONG_PROXY_URL, timeout=10)
    response.raise_for_status()
    candidates = response.json().get("data", [])
    if not candidates:
        return None
    proxy = random.choice(candidates)
    username, password = proxy.get("username"), proxy.get("password")
    host, port = proxy.get("ip"), proxy.get("port")
    if not all((username, password, host, port)):
        raise ValueError("Proxy pool returned incomplete proxy credentials")
    proxy_url = f"http://{quote(str(username), safe='')}:{quote(str(password), safe='')}@{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def _pad(value: bytes) -> bytes:
    size = AES.block_size - len(value) % AES.block_size
    return value + bytes([size]) * size


def _unpad(value: bytes) -> bytes:
    if not value or value[-1] < 1 or value[-1] > AES.block_size:
        raise ValueError("invalid PKCS#7 padding")
    size = value[-1]
    if value[-size:] != bytes([size]) * size:
        raise ValueError("invalid PKCS#7 padding")
    return value[:-size]


def _encrypt_text(value: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES_MODE, iv)
    encoded = base64.b64encode(cipher.encrypt(_pad(value.encode("utf-8")))).decode("ascii")
    return encoded.replace("/", "_")


def _decrypt_text(value: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES_MODE, iv)
    raw = base64.b64decode(value.replace("_", "/"), validate=True)
    return _unpad(cipher.decrypt(raw)).decode("utf-8")


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _javascript_random_string() -> str:
    first = _base36(int(random.random() * 36**10))[-8:]
    second = _base36(int(random.random() * 36**10))[-8:]
    return f"{first}-{second}{int(time.time() * 1000)}"


def derive_session_key() -> bytes:
    encrypted = _encrypt_text(KEY_SEED, FIXED_KEY, FIXED_IV)
    return encrypted[4:20].encode("ascii")


def make_etag() -> str:
    encrypted = _encrypt_text(_javascript_random_string(), FIXED_KEY, FIXED_IV)
    return encrypted.replace("_", "", 1)[1:17]


@dataclass
class SessionResult:
    request_data: dict[str, Any]
    encrypted_request: str
    encrypted_response: str
    response_data: dict[str, Any]
    etag: str
    response: requests.Response


class BdiaSessionClient:
    def __init__(
        self,
        user_agent: str | None = None,
        timeout: float = 30,
        proxies: dict[str, str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
        )
        self.http = requests.Session()
        if proxies:
            self.http.proxies.update(proxies)
        self.http.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json; charset=utf-8",
                "Origin": "https://www.bdia.com.cn",
                "Referer": "https://www.bdia.com.cn/",
                "User-Agent": self.user_agent,
            }
        )
        self.session_key = derive_session_key()

    def build_payload(
        self,
        url: str = "https://www.bdia.com.cn/#/flightdep",
        *,
        uuid_value: str | None = None,
        user_id: str | None = None,
        is_post: bool = False,
        post_body: str = "",
        time_zone: str = "Asia/Shanghai",
        tab_id: str | None = None,
        referrer: str = "https://www.bdia.com.cn/",
        is_reload: bool = False,
        doc_type: str = "<!DOCTYPE html>",
        screen_width: int = 1920,
        screen_height: int = 1040,
        window_width: int = 1920,
        window_height: int = 1040,
        zoom_factor: float = 1.0,
        dpr: float = 1.0,
    ) -> dict[str, Any]:
        user_id = user_id or _base36(int(random.random() * 36**10))[-8:]
        tab_id = tab_id or _base36(int(random.random() * 36**10))[-10:]
        return {
            "uuid": uuid_value or str(uuid.uuid4()),
            "url": url,
            "cid": user_id,
            "_": f"{self.user_agent}|{user_id}",
            "common": {
                "isPost": is_post,
                "postBody": post_body,
                "timeZone": time_zone,
                "tabId": tab_id,
                "referrer": referrer,
                "isReload": is_reload,
                "docType": doc_type,
                "screenWidth": screen_width,
                "screenHeight": screen_height,
                "windowWidth": window_width,
                "windowHeight": window_height,
                "cookies": None,
                "zoomFactor": zoom_factor,
                "dpr": dpr,
                "userAgent": self.user_agent,
                "platform": "Win32",
                "language": "zh-CN",
                "languages": "zh-CN,zh,en",
            },
            "extension": {"reuse": False, "simMode": False},
        }

    def create_session(self, payload: dict[str, Any] | None = None) -> SessionResult:
        payload = payload or self.build_payload()
        etag = make_etag()
        encrypted_request = _encrypt_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), self.session_key, etag.encode("ascii"))
        response = self.http.post(
            SESSIONS_URL,
            headers={"Fetch-Mode": self.user_agent, "etag": etag},
            json={"data": encrypted_request},
            timeout=self.timeout,
        )
        response.raise_for_status()
        response_json = response.json()
        encrypted_response = response_json["data"].replace("\n", "")
        decoded = _decrypt_text(encrypted_response, self.session_key, etag.encode("ascii"))
        response_data = json.loads(decoded)
        return SessionResult(payload, encrypted_request, encrypted_response, response_data, etag, response)


def create_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return BdiaSessionClient().create_session(payload).response_data


class _MessagePack:
    @staticmethod
    def encode(value: Any) -> bytes:
        if value is None:
            return b"\xc0"
        if value is False:
            return b"\xc2"
        if value is True:
            return b"\xc3"
        if isinstance(value, int):
            if 0 <= value <= 0x7F:
                return bytes([value])
            if -32 <= value < 0:
                return bytes([value & 0xFF])
            if 0 <= value <= 0xFF:
                return b"\xcc" + value.to_bytes(1, "big")
            if 0 <= value <= 0xFFFF:
                return b"\xcd" + value.to_bytes(2, "big")
            if 0 <= value <= 0xFFFFFFFF:
                return b"\xce" + value.to_bytes(4, "big")
            if value >= 0:
                return b"\xcf" + value.to_bytes(8, "big")
            if value >= -128:
                return b"\xd0" + value.to_bytes(1, "big", signed=True)
            if value >= -32768:
                return b"\xd1" + value.to_bytes(2, "big", signed=True)
            if value >= -2147483648:
                return b"\xd2" + value.to_bytes(4, "big", signed=True)
            return b"\xd3" + value.to_bytes(8, "big", signed=True)
        if isinstance(value, float):
            return b"\xcb" + struct.pack(">d", value)
        if isinstance(value, str):
            raw = value.encode("utf-8")
            size = len(raw)
            if size < 32:
                return bytes([0xA0 | size]) + raw
            if size <= 0xFF:
                return b"\xd9" + bytes([size]) + raw
            if size <= 0xFFFF:
                return b"\xda" + size.to_bytes(2, "big") + raw
            return b"\xdb" + size.to_bytes(4, "big") + raw
        if isinstance(value, (bytes, bytearray)):
            raw = bytes(value)
            if len(raw) <= 0xFF:
                return b"\xc4" + bytes([len(raw)]) + raw
            if len(raw) <= 0xFFFF:
                return b"\xc5" + len(raw).to_bytes(2, "big") + raw
            return b"\xc6" + len(raw).to_bytes(4, "big") + raw
        if isinstance(value, (list, tuple)):
            size = len(value)
            prefix = bytes([0x90 | size]) if size < 16 else b"\xdc" + size.to_bytes(2, "big")
            return prefix + b"".join(_MessagePack.encode(item) for item in value)
        if isinstance(value, dict):
            size = len(value)
            prefix = bytes([0x80 | size]) if size < 16 else b"\xde" + size.to_bytes(2, "big")
            return prefix + b"".join(_MessagePack.encode(k) + _MessagePack.encode(v) for k, v in value.items())
        raise TypeError(f"unsupported MessagePack value: {type(value)!r}")

    @staticmethod
    def decode(data: bytes) -> Any:
        class Reader:
            def __init__(self, raw: bytes) -> None:
                self.raw = raw
                self.pos = 0

            def take(self, size: int) -> bytes:
                value = self.raw[self.pos : self.pos + size]
                self.pos += size
                return value

            def uint(self, size: int) -> int:
                return int.from_bytes(self.take(size), "big")

            def one(self) -> Any:
                code = self.uint(1)
                if code <= 0x7F:
                    return code
                if code >= 0xE0:
                    return code - 256
                if 0xA0 <= code <= 0xBF:
                    return self.take(code & 31).decode("utf-8")
                if 0x90 <= code <= 0x9F:
                    return [self.one() for _ in range(code & 15)]
                if 0x80 <= code <= 0x8F:
                    return {self.one(): self.one() for _ in range(code & 15)}
                if code == 0xC0:
                    return None
                if code == 0xC2:
                    return False
                if code == 0xC3:
                    return True
                if code == 0xCA:
                    return struct.unpack(">f", self.take(4))[0]
                if code == 0xCB:
                    return struct.unpack(">d", self.take(8))[0]
                if code == 0xCC:
                    return self.uint(1)
                if code == 0xCD:
                    return self.uint(2)
                if code == 0xCE:
                    return self.uint(4)
                if code == 0xCF:
                    return self.uint(8)
                if code == 0xD0:
                    return int.from_bytes(self.take(1), "big", signed=True)
                if code == 0xD1:
                    return int.from_bytes(self.take(2), "big", signed=True)
                if code == 0xD2:
                    return int.from_bytes(self.take(4), "big", signed=True)
                if code == 0xD3:
                    return int.from_bytes(self.take(8), "big", signed=True)
                if code == 0xC4:
                    return self.take(self.uint(1))
                if code == 0xC5:
                    return self.take(self.uint(2))
                if code == 0xC6:
                    return self.take(self.uint(4))
                if code == 0xD9:
                    return self.take(self.uint(1)).decode("utf-8")
                if code == 0xDA:
                    return self.take(self.uint(2)).decode("utf-8")
                if code == 0xDB:
                    return self.take(self.uint(4)).decode("utf-8")
                if code == 0xDC:
                    return [self.one() for _ in range(self.uint(2))]
                if code == 0xDD:
                    return [self.one() for _ in range(self.uint(4))]
                if code == 0xDE:
                    return {self.one(): self.one() for _ in range(self.uint(2))}
                if code == 0xDF:
                    return {self.one(): self.one() for _ in range(self.uint(4))}
                raise ValueError(f"unsupported MessagePack code: 0x{code:02x}")

        return Reader(data).one()


def _ancestor_classes(nodes: dict[str, dict[str, Any]], parent: str | None) -> list[str]:
    classes = []
    while parent:
        node = nodes.get(parent, {})
        classes.extend(
            attribute["value"]
            for attribute in node.get("attributes", [])
            if attribute.get("name") == "class"
        )
        parent = node.get("parent")
    return classes


def _ancestor_ids(nodes: dict[str, dict[str, Any]], parent: str | None) -> list[str]:
    result = []
    while parent:
        result.append(parent)
        parent = nodes.get(parent, {}).get("parent")
    return result


def extract_flight_cards(
    patch: dict[str, Any], excluded_block_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    nodes = {
        item["nid"]: item
        for item in patch.get("list", [])
        if item.get("commandCode") == 8 and item.get("nid")
    }
    cards: dict[str, dict[str, Any]] = {}
    for item in patch.get("list", []):
        if item.get("commandCode") != 16 or not item.get("textContent", "").strip():
            continue
        classes = _ancestor_classes(nodes, item.get("parent"))
        block_id = next(
            (
                node_id
                for node_id in _ancestor_ids(nodes, item.get("parent"))
                if "flight-block"
                in " ".join(
                    attribute["value"]
                    for attribute in nodes.get(node_id, {}).get("attributes", [])
                    if attribute.get("name") == "class"
                )
            ),
            None,
        )
        if block_id is None or block_id in (excluded_block_ids or set()):
            continue
        card = cards.setdefault(block_id, {"text": []})
        text = item["textContent"].strip()
        card["text"].append(text)
        class_text = " ".join(classes)
        if "plan-time" in class_text:
            card["plannedTime"] = text
        elif "actual-time" in class_text:
            card["actualTime"] = text.removeprefix("实际")
        elif "company-name" in class_text:
            card.setdefault("airlineName", []).append(text)
        elif "airline-code" in class_text:
            card.setdefault("flightNo", []).append(text)
        elif "destination-place" in class_text:
            card["destination"] = text
        elif "checkin-box" in class_text:
            card.setdefault("checkInDesk", []).append(text)
        elif "boarding-box" in class_text:
            card.setdefault("boardingGate", []).append(text)
        elif "takeoff-state" in class_text:
            card["flightStatus"] = text
    for card in cards.values():
        for key in ("airlineName", "flightNo", "checkInDesk", "boardingGate"):
            if key in card:
                card[key] = ",".join(card[key])
    return list(cards.values())


class BdiaFlightClient:
    def __init__(
        self,
        timeout: float = 30,
        user_agent: str | None = None,
        proxies: dict[str, str] | None = None,
    ) -> None:
        self.proxies = proxies
        self.session_client = BdiaSessionClient(user_agent=user_agent, timeout=timeout, proxies=proxies)
        self.timeout = timeout
        self.failed_requests: dict[tuple[str, int], str] = {}

    @staticmethod
    def _get_frame_messages(frame: bytes) -> list[Any]:
        messages = _MessagePack.decode(frame)
        if isinstance(messages, list) and messages and isinstance(messages[0], int):
            return [messages]
        return messages if isinstance(messages, list) else []

    @staticmethod
    def _ack_heartbeat(socket: Any, message: Any, next_sequence: int) -> bool:
        if (
            isinstance(message, list)
            and len(message) > 1
            and message[0] == -1
            and isinstance(message[1], list)
            and len(message[1]) > 1
            and message[1][1] == 32
        ):
            socket.send(_MessagePack.encode([-1, ["", "", 32, next_sequence, False]]), opcode=2)
            return True
        return False

    @staticmethod
    def _merge_dom_patch(
        patch: dict[str, Any],
        nodes: dict[str, dict[str, Any]],
        text_nodes: dict[str, dict[str, Any]],
    ) -> None:
        for item in patch.get("list", []):
            command = item.get("commandCode")
            node_id = item.get("nid")
            if command == 8 and node_id:
                nodes[str(node_id)] = item
            elif command in (16, 17) and node_id:
                text_nodes[str(node_id)] = item
            elif command == 19 and node_id:
                node = nodes.get(str(node_id))
                if not node:
                    continue
                attributes = {attribute.get("name"): attribute for attribute in node.get("attributes", [])}
                for change in item.get("attrs", []):
                    name = change.get("name")
                    if not name:
                        continue
                    if change.get("code") == "remove":
                        attributes.pop(name, None)
                    else:
                        attributes[name] = {
                            "name": name,
                            "value": change.get("value", ""),
                            "namespaceURI": change.get("namespaceURI", ""),
                        }
                node["attributes"] = list(attributes.values())

    @classmethod
    def _clear_flight_dom(
        cls,
        nodes: dict[str, dict[str, Any]],
        text_nodes: dict[str, dict[str, Any]],
    ) -> set[str]:
        flight_blocks = {
            node_id
            for node_id, node in nodes.items()
            if "flight-block" in cls._node_classes(node)
        }
        if not flight_blocks:
            return set()

        def belongs_to_flight(node: dict[str, Any]) -> bool:
            parent_id = node.get("parent")
            while parent_id:
                if parent_id in flight_blocks:
                    return True
                parent_id = nodes.get(str(parent_id), {}).get("parent")
            return False

        for node_id, node in list(nodes.items()):
            if node_id in flight_blocks or belongs_to_flight(node):
                nodes.pop(node_id, None)
        for node_id, node in list(text_nodes.items()):
            if belongs_to_flight(node):
                text_nodes.pop(node_id, None)
        return flight_blocks

    @staticmethod
    def _node_classes(node: dict[str, Any]) -> str:
        return " ".join(
            attribute.get("value", "")
            for attribute in node.get("attributes", [])
            if attribute.get("name") == "class"
        )

    @classmethod
    def _find_date_controls(
        cls,
        nodes: dict[str, dict[str, Any]],
        text_nodes: dict[str, dict[str, Any]],
    ) -> tuple[str | None, dict[str, str], str | None]:
        selector_id = next(
            (
                node_id
                for node_id, node in nodes.items()
                if "el-select mar15 w204" in cls._node_classes(node)
            ),
            None,
        )
        options: dict[str, str] = {}
        selected_label = None
        for text_node in text_nodes.values():
            label = text_node.get("textContent", "").strip()
            if not label or " (" not in label:
                continue
            parent = text_node.get("parent")
            while parent:
                node = nodes.get(str(parent), {})
                classes = cls._node_classes(node)
                if node.get("tag") == "li" and "el-select-dropdown__item" in classes:
                    options[label] = str(parent)
                    if "selected" in classes.split():
                        selected_label = label
                    break
                parent = node.get("parent")
        if selector_id:
            selector_id = next(
                (
                    node_id
                    for node_id, node in nodes.items()
                    if node.get("tag") == "input"
                    and nodes.get(node.get("parent"), {}).get("parent") == selector_id
                ),
                selector_id,
            )
        options = {
            label: next(
                (
                    node_id
                    for node_id, node in nodes.items()
                    if node.get("parent") == option_id and node.get("tag") == "span"
                ),
                option_id,
            )
            for label, option_id in options.items()
        }
        return selector_id, options, selected_label

    @staticmethod
    def _send_click(socket: Any, sequence: int, tab_id: str, node_id: str) -> int:
        for event in ("pointerdown", "mousedown", "pointerup", "mouseup", "click"):
            values = [4, "1", str(node_id), event, 20.5, 10.5, 1, 0, 0, 0, "", 0, 0, 0, 0, 20, 10, 20, 10, 20, 10, True]
            if event.startswith("pointer"):
                values[8] = int(event == "pointerdown")
                values.extend([1, 1, True, "mouse", 0.5 if event == "pointerdown" else 0, 0, 0, 0, 0, 1])
            elif event != "click":
                values[8] = int(event == "mousedown")
                values = values[:17] + [str(node_id)] + values[17:] + ["", 0, 0]
            sequence += 1
            socket.send(_MessagePack.encode([sequence, [tab_id, "1", *values]]), opcode=2)
            time.sleep(0.07)
        return sequence

    @staticmethod
    def _send_wheel(socket: Any, sequence: int, tab_id: str, node_id: str) -> int:
        values = [4, "1", str(node_id), "wheel", 768, 112, 0, 0, 150, 0, -179, -179, 0, 120]
        sequence += 1
        socket.send(_MessagePack.encode([sequence, [tab_id, "1", *values]]), opcode=2)
        return sequence

    @staticmethod
    def _send_scroll(
        socket: Any,
        sequence: int,
        tab_id: str,
        root_id: str,
        scroll_y: int,
        document_height: int,
    ) -> int:
        values = [4, "1", str(root_id), "scroll", 0, scroll_y, 2868, document_height, False, False, True, None]
        sequence += 1
        socket.send(_MessagePack.encode([sequence, [tab_id, "1", *values]]), opcode=2)
        return sequence

    @classmethod
    def _find_load_more(cls, nodes: dict[str, dict[str, Any]]) -> str | None:
        button_id = next(
            (node_id for node_id, node in nodes.items() if "selectmore" in cls._node_classes(node).split()),
            None,
        )
        if not button_id:
            return None
        return next(
            (
                node_id
                for node_id, node in nodes.items()
                if str(node.get("parent")) == button_id and node.get("tag") == "span"
            ),
            button_id,
        )

    def _scroll_collect_flights(
        self,
        socket: Any,
        sequence: int,
        tab_id: str,
        flights: list[dict[str, Any]],
        nodes: dict[str, dict[str, Any]],
        text_nodes: dict[str, dict[str, Any]],
        next_server_sequence: int,
        excluded_block_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        collected: dict[tuple[str, str], dict[str, Any]] = {}

        def add_flights(items: list[dict[str, Any]]) -> int:
            added = 0
            for item in items:
                flight_number = item.get("flightNo", "").strip()
                planned_time = item.get("plannedTime", "").strip()
                if not flight_number:
                    continue
                key = (flight_number, planned_time)
                if key not in collected:
                    collected[key] = item
                    added += 1
            return added

        add_flights(flights)
        socket.settimeout(min(0.5, self.timeout))
        for _ in range(100):
            button_id = self._find_load_more(nodes)
            if not button_id:
                break
            before_count = len(collected)
            sequence = self._send_click(socket, sequence, tab_id, button_id)
            deadline = time.monotonic() + min(15.0, self.timeout)
            first_new_flight_at = None
            idle_after_update = 0
            while time.monotonic() < deadline:
                try:
                    frame = socket.recv()
                except WebSocketTimeoutException:
                    if first_new_flight_at is not None:
                        idle_after_update += 1
                        if idle_after_update >= 2:
                            break
                    continue
                if not frame or isinstance(frame, str):
                    continue
                for message in self._get_frame_messages(frame):
                    if self._ack_heartbeat(socket, message, next_server_sequence):
                        continue
                    if not isinstance(message, list) or len(message) < 2 or not isinstance(message[1], list):
                        continue
                    if isinstance(message[0], int) and message[0] >= 0:
                        next_server_sequence = max(next_server_sequence, message[0] + 1)
                    payload = message[1]
                    if len(payload) < 3 or not isinstance(payload[2], str):
                        continue
                    try:
                        patch = json.loads(payload[2])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(patch, dict):
                        continue
                    self._merge_dom_patch(patch, nodes, text_nodes)
                    merged_dom = {"list": [*nodes.values(), *text_nodes.values()]}
                    add_flights(extract_flight_cards(merged_dom, excluded_block_ids))
                    if len(collected) > before_count:
                        first_new_flight_at = first_new_flight_at or time.monotonic()
                        idle_after_update = 0
                if first_new_flight_at is not None and time.monotonic() - first_new_flight_at > 3:
                    break
            if len(collected) == before_count:
                break
        return list(collected.values())

    @staticmethod
    def _target_date(date_offset: int) -> date:
        if date_offset not in (-1, 0, 1):
            raise ValueError("date_offset must be -1, 0, or 1")
        return datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=date_offset)

    def _receive_flights_once(
        self,
        direction: str | int = "departure",
        date_offset: int = 0,
    ) -> list[dict[str, Any]]:
        direction_routes = {
            "departure": ("flightdep", "出发航班"),
            "arrival": ("flightarr", "到达航班"),
            0: ("flightdep", "出发航班"),
            1: ("flightarr", "到达航班"),
        }
        if direction not in direction_routes:
            raise ValueError("direction must be 'departure', 'arrival', 0, or 1")
        route, direction_label = direction_routes[direction]
        target_date = self._target_date(date_offset)
        day_label = {-1: "昨天", 0: "今天", 1: "明天"}[date_offset]
        option_label = f"{target_date.isoformat()} ({day_label})"
        page_url = f"https://www.bdia.com.cn/#/{route}"
        self.session_client.http.cookies.clear()
        payload = self.session_client.build_payload(url=page_url)
        session = self.session_client.create_session(payload)
        if session.response_data.get("uuid") != session.request_data["uuid"]:
            raise RuntimeError("server reused a previous session despite fresh cookies")
        raw_token = session.response_data.get("token")
        if not isinstance(raw_token, str) or not raw_token:
            raise RuntimeError(f"session has no WebSocket token: {session.response_data.get('status')}")
        token = quote(raw_token, safe="")
        tab_id = session.request_data["common"]["tabId"]
        session_uuid = session.request_data["uuid"]
        websocket_url = f"wss://{BASE_URL.removeprefix('https://')}/pr/{token}/b/ws/{tab_id}/{session_uuid}"
        cookies = "; ".join(f"{key}={value}" for key, value in self.session_client.http.cookies.get_dict().items())
        proxy_options: dict[str, Any] = {}
        proxy_url = self.proxies.get("https") if self.proxies else None
        if proxy_url:
            proxy = urlsplit(proxy_url)
            proxy_options = {
                "http_proxy_host": proxy.hostname,
                "http_proxy_port": proxy.port,
                "http_proxy_auth": (unquote(proxy.username or ""), unquote(proxy.password or "")),
                "http_proxy_type": "http",
            }
        socket = create_connection(
            websocket_url,
            timeout=self.timeout,
            origin="https://www.bdia.com.cn",
            cookie=cookies,
            header=[f"User-Agent: {self.session_client.user_agent}"],
            **proxy_options,
        )
        try:
            socket.send(_MessagePack.encode([1, [tab_id, "", 0, "visible", True]]), opcode=2)
            sequence = 1
            nodes: dict[str, dict[str, Any]] = {}
            text_nodes: dict[str, dict[str, Any]] = {}
            initial_flights: list[dict[str, Any]] = []
            selector_id = None
            options: dict[str, str] = {}
            selected_label = None
            next_server_sequence = 1
            initial_deadline = time.monotonic() + self.timeout
            while time.monotonic() < initial_deadline:
                try:
                    frame = socket.recv()
                except WebSocketTimeoutException:
                    continue
                if not frame:
                    break
                if isinstance(frame, str):
                    continue
                for message in self._get_frame_messages(frame):
                    if self._ack_heartbeat(socket, message, next_server_sequence):
                        continue
                    if not isinstance(message, list) or len(message) < 2 or not isinstance(message[1], list):
                        continue
                    if isinstance(message[0], int) and message[0] >= 0:
                        next_server_sequence = max(next_server_sequence, message[0] + 1)
                    payload_data = message[1]
                    if len(payload_data) < 3 or not isinstance(payload_data[2], str):
                        continue
                    try:
                        patch = json.loads(payload_data[2])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(patch, dict):
                        continue
                    self._merge_dom_patch(patch, nodes, text_nodes)
                    found = extract_flight_cards(patch)
                    if found:
                        initial_flights = found
                    selector_id, options, selected_label = self._find_date_controls(nodes, text_nodes)
                if initial_flights and selector_id and option_label in options:
                    break

            if not selector_id or option_label not in options:
                raise RuntimeError(f"date selector option not found: {option_label}")
            if selected_label == option_label:
                return self._scroll_collect_flights(
                    socket, sequence, tab_id, initial_flights, nodes, text_nodes, next_server_sequence
                )

            sequence = self._send_click(socket, sequence, tab_id, selector_id)
            time.sleep(0.5)
            stale_flight_block_ids = self._clear_flight_dom(nodes, text_nodes)
            sequence = self._send_click(socket, sequence, tab_id, options[option_label])

            result_deadline = time.monotonic() + self.timeout
            while time.monotonic() < result_deadline:
                try:
                    frame = socket.recv()
                except WebSocketTimeoutException:
                    continue
                if not frame or isinstance(frame, str):
                    continue
                for message in self._get_frame_messages(frame):
                    if self._ack_heartbeat(socket, message, next_server_sequence):
                        continue
                    if not isinstance(message, list) or len(message) < 2 or not isinstance(message[1], list):
                        continue
                    if isinstance(message[0], int) and message[0] >= 0:
                        next_server_sequence = max(next_server_sequence, message[0] + 1)
                    payload_data = message[1]
                    if len(payload_data) < 3 or not isinstance(payload_data[2], str):
                        continue
                    try:
                        patch = json.loads(payload_data[2])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(patch, dict):
                        continue
                    self._merge_dom_patch(patch, nodes, text_nodes)
                    flights = extract_flight_cards(patch, stale_flight_block_ids)
                    _, _, selected_label = self._find_date_controls(nodes, text_nodes)
                    if flights and selected_label == option_label:
                        return self._scroll_collect_flights(
                            socket,
                            sequence,
                            tab_id,
                            flights,
                            nodes,
                            text_nodes,
                            next_server_sequence,
                            stale_flight_block_ids,
                        )
                    if selected_label == option_label and any(
                        item.get("commandCode") == 16
                        and item.get("textContent", "").strip()
                        in ("暂无航班记录。", "查询不到任何航班记录。")
                        for item in patch.get("list", [])
                    ):
                        return []
            raise TimeoutError(f"flight list did not update for {direction_label}, {option_label}")
        finally:
            socket.close()

    def receive_flights(
        self,
        direction: str | int = "departure",
        date_offset: int = 0,
    ) -> list[dict[str, Any]]:
        self._target_date(date_offset)
        if direction not in ("departure", "arrival", 0, 1):
            raise ValueError("direction must be 'departure', 'arrival', 0, or 1")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._receive_flights_once(direction, date_offset)
            except (RuntimeError, TimeoutError, WebSocketTimeoutException, WebSocketBadStatusException) as error:
                last_error = error
                if isinstance(error, WebSocketBadStatusException) and error.status_code not in (429, 500, 502, 503, 504):
                    break
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"failed to load flights: {direction}, {date_offset}") from last_error

    def collect_all(
        self,
        output_dir: str | Path | None = None,
        directions: tuple[str, ...] = ("departure", "arrival"),
        date_offsets: tuple[int, ...] = (-1, 0, 1),
    ) -> list[Path]:
        output_path = Path(output_dir) if output_dir else Path(__file__).parent / "flight_list_output"
        output_path.mkdir(parents=True, exist_ok=True)
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        date_names = {-1: "yesterday", 0: "today", 1: "tomorrow"}
        direction_names = {"departure": "出发航班", "arrival": "到达航班"}
        saved_files = []
        self.failed_requests = {}
        for direction in directions:
            for date_offset in date_offsets:
                target_date = today + timedelta(days=date_offset)
                try:
                    flights = self.receive_flights(direction=direction, date_offset=date_offset)
                except (RuntimeError, TimeoutError, WebSocketTimeoutException, WebSocketBadStatusException) as error:
                    cause = error.__cause__ or error
                    reason = (
                        f"WebSocket handshake HTTP {cause.status_code}"
                        if isinstance(cause, WebSocketBadStatusException)
                        else str(cause)
                    )
                    self.failed_requests[(direction, date_offset)] = reason
                    continue
                output = {
                    "date": target_date.isoformat(),
                    "dateOffset": date_offset,
                    "direction": direction,
                    "type": direction_names[direction],
                    "count": len(flights),
                    "flights": flights,
                }
                filename = f"{direction}_{date_names[date_offset]}_{target_date.isoformat()}.json"
                file_path = output_path / filename
                file_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
                saved_files.append(file_path)
        return saved_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", default="")
    arguments = parser.parse_args()
    proxies = get_long_proxy()
    if not proxies:
        raise SystemExit("Proxy pool returned no proxy")
    client = BdiaFlightClient(proxies=proxies)

    if arguments.jsonl:
        output_path = Path(arguments.jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        direction_names = {"departure": "出发航班", "arrival": "到达航班"}
        client.failed_requests = {}
        with output_path.open("w", encoding="utf-8") as output_file:
            for direction in ("departure", "arrival"):
                for date_offset in (-1, 0, 1):
                    target_date = today + timedelta(days=date_offset)
                    try:
                        flights = client.receive_flights(direction, date_offset)
                    except (RuntimeError, TimeoutError, WebSocketTimeoutException, WebSocketBadStatusException) as error:
                        cause = error.__cause__ or error
                        reason = (
                            f"WebSocket handshake HTTP {cause.status_code}"
                            if isinstance(cause, WebSocketBadStatusException)
                            else str(cause)
                        )
                        client.failed_requests[(direction, date_offset)] = reason
                        continue
                    for flight in flights:
                        item = {
                            "date": target_date.isoformat(),
                            "dateOffset": date_offset,
                            "direction": direction,
                            "type": direction_names[direction],
                            **flight,
                        }
                        output_file.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(output_path)
    else:
        for file_path in client.collect_all():
            print(file_path)

    if client.failed_requests:
        for (direction, date_offset), reason in client.failed_requests.items():
            print(f"Failed: {direction}, {date_offset}: {reason}", file=sys.stderr)
        raise SystemExit(1)


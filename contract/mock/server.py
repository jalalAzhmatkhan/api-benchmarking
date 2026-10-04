#!/usr/bin/env python3
"""Reference implementation of the /items contract, in memory, stdlib only.

It exists ONLY to self-test contract/conformance.js in CI and locally. It is not a benchmarked
service. Spec: Documentation/specs/api-contract.md.
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# MOCK_BUG injects one deliberate contract violation so CI can prove conformance.js detects it:
#   status422 | no_location | put_merge | delete_200 | accept_float
BUG = os.environ.get("MOCK_BUG", "")
MAX_ID = 9_007_199_254_740_991
MAX_PRICE = 9_007_199_254_740_991
MAX_QTY = 2_147_483_647
# SEED_ROWS=N pre-"loads" ids 1..N with the same values as db/seed/seed.sql (synthesized lazily), so
# the load-test scenarios can read seeded rows against the mock.
SEED_ROWS = int(os.environ.get("SEED_ROWS", "0"))
_SEED_TS = "2026-01-01T00:00:00Z"
_gone: set[int] = set()
_lock = threading.Lock()
_items: dict[int, dict] = {}
_next_id = 100_001


def _load(item_id: int):
    """Return the item (materializing a seed row on first touch) or None. Caller holds _lock."""
    item = _items.get(item_id)
    if item is None and 1 <= item_id <= SEED_ROWS and item_id not in _gone:
        item = {"id": item_id, "name": f"item-{item_id}",
                "description": None if item_id % 10 == 0 else "desc-" + hashlib.md5(str(item_id).encode()).hexdigest(),
                "price_cents": (item_id * 37) % 1_000_000, "quantity": item_id % 1000,
                "created_at": _SEED_TS, "updated_at": _SEED_TS}
        _items[item_id] = item
    return item


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate(body) -> str | None:
    if not isinstance(body, dict):
        return "body must be an object"
    name = body.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        return "name must be a string of 1-100 characters"
    if "description" in body and body["description"] is not None:
        d = body["description"]
        if not isinstance(d, str) or len(d) > 1000:
            return "description must be null or a string of at most 1000 characters"
    p = body.get("price_cents")
    if BUG == "accept_float" and isinstance(p, float):
        return None
    if not _is_int(p) or not 0 <= p <= MAX_PRICE:
        return "price_cents must be an integer in 0..9007199254740991"
    q = body.get("quantity")
    if not _is_int(q) or not 0 <= q <= MAX_QTY:
        return "quantity must be an integer in 0..2147483647"
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mock"

    def log_message(self, *args):  # per-request logging off (benchmark rule)
        pass

    def handle_one_request(self):
        self.__dict__.pop("_raw", None)  # fresh body cache per request on a keep-alive connection
        super().handle_one_request()

    def handle(self):
        try:
            super().handle()
        except ConnectionError:  # client closed the socket (readiness probes, k6 teardown)
            pass

    def _send(self, status: int, payload=None, headers=None):
        raw = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if status != 204:
            self.wfile.write(raw)

    def _error(self, status: int, code: str, message: str):
        if BUG == "status422" and status == 400:
            status = 422
        self._send(status, {"error": {"code": code, "message": message}})

    def _body(self):
        # Always drain the request body first, even when answering 400/404 early; otherwise the
        # unread bytes corrupt the next request on this keep-alive connection.
        if not hasattr(self, "_raw"):
            n = int(self.headers.get("Content-Length") or 0)
            self._raw = self.rfile.read(n) if n else b""
        return self._raw

    def _id(self, path: str):
        m = re.fullmatch(r"/items/([^/]+)", path)
        if not m:
            return None, False
        s = m.group(1)
        if not re.fullmatch(r"[0-9]+", s) or not 1 <= int(s) <= MAX_ID:
            self._error(400, "VALIDATION_ERROR", "invalid id")
            return None, True
        return int(s), False

    def _parse(self):
        try:
            return json.loads(self._body().decode("utf-8")), None
        except (ValueError, UnicodeDecodeError):
            return None, "malformed JSON"

    def do_GET(self):
        item_id, handled = self._id(self.path)
        if handled:
            return
        if item_id is None:
            return self._error(404, "NOT_FOUND", "no such route")
        with _lock:
            item = _load(item_id)
            item = dict(item) if item else None
        if item is None:
            return self._error(404, "NOT_FOUND", "item not found")
        self._send(200, item)

    def do_POST(self):
        global _next_id
        if self.path != "/items":
            return self._error(404, "NOT_FOUND", "no such route")
        body, err = self._parse()
        err = err or validate(body)
        if err:
            return self._error(400, "VALIDATION_ERROR", err)
        with _lock:
            item_id, _next_id = _next_id, _next_id + 1
            now = _now()
            item = {"id": item_id, "name": body["name"], "description": body.get("description"),
                    "price_cents": body["price_cents"], "quantity": body["quantity"],
                    "created_at": now, "updated_at": now}
            _items[item_id] = item
        self._send(201, item, None if BUG == "no_location" else {"Location": f"/items/{item_id}"})

    def do_PUT(self):
        self._body()
        item_id, handled = self._id(self.path)
        if handled:
            return
        if item_id is None:
            return self._error(404, "NOT_FOUND", "no such route")
        body, err = self._parse()
        err = err or validate(body)
        if err:
            return self._error(400, "VALIDATION_ERROR", err)
        with _lock:
            item = _load(item_id)
            if item is None:
                return self._error(404, "NOT_FOUND", "item not found")
            description = body.get("description", item["description"]) if BUG == "put_merge" else body.get("description")
            item.update(name=body["name"], description=description,
                        price_cents=body["price_cents"], quantity=body["quantity"], updated_at=_now())
            out = dict(item)
        self._send(200, out)

    def do_DELETE(self):
        item_id, handled = self._id(self.path)
        if handled:
            return
        if item_id is None:
            return self._error(404, "NOT_FOUND", "no such route")
        with _lock:
            existed = _load(item_id) is not None
            if existed:
                _items.pop(item_id)
                _gone.add(item_id)
        if not existed:
            return self._error(404, "NOT_FOUND", "item not found")
        if BUG == "delete_200":
            return self._send(200, {"deleted": True})
        self._send(204)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

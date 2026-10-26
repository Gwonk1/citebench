# Syfert MCP client for the raw Syfert arm of the trap benchmark.
# Auth is the mcpbench mechanism (~/projects/mcpbench/lib/mcp.py): Authorization: Bearer <SYFERT_MCP_TOKEN>,
# read from the environment or ~/projects/mcpbench/keys.env, plus X-Syfert-Bench: 1 so the server keeps
# these calls out of the cite-miss ledger. The token is never printed. One call at a time, paced.
import json
import os
import time
import urllib.error
import urllib.request

URL = "https://mcp.syfert.com/mcp"
KEYS = os.path.expanduser("~/projects/mcpbench/keys.env")
UA = "not-unfair-legal-benchmark/1.1 (raw Syfert MCP arm, read-only)"
MIN_GAP = 1.5  # seconds between calls: at most 40 per minute
_last = [0.0]
_state = {"session": None, "id": 0, "server_info": None}


def _token():
    tok = os.environ.get("SYFERT_MCP_TOKEN")
    if tok:
        return tok
    for line in open(KEYS, encoding="utf-8"):
        if line.startswith("SYFERT_MCP_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("SYFERT_MCP_TOKEN missing (keys.env)")


def _post(payload, expect_reply=True, timeout=240):
    gap = time.monotonic() - _last[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    headers = {
        "Authorization": "Bearer " + _token(),
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": UA,
        "X-Syfert-Bench": "1",
    }
    if _state["session"]:
        headers["Mcp-Session-Id"] = _state["session"]
    last = None
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status, raw, rh = resp.status, resp.read().decode(), resp.headers
        except urllib.error.HTTPError as e:
            status, raw, rh = e.code, e.read().decode(errors="replace"), e.headers
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"network: {type(e).__name__}: {str(e)[:160]}"
            _last[0] = time.monotonic()
            time.sleep(5 * (attempt + 1))
            continue
        _last[0] = time.monotonic()
        if status in (429, 502, 503, 504) and attempt < 2:
            last = f"HTTP {status}"
            time.sleep(15 * (attempt + 1))
            continue
        break
    else:
        raise RuntimeError(last or "transport failure")
    sid = rh.get("mcp-session-id") if rh else None
    if sid:
        _state["session"] = sid
    if not expect_reply:
        return None
    if status != 200:
        raise RuntimeError(f"HTTP {status}: {raw[:200]}")
    msg = None
    if "data:" in raw[:200] or "text/event-stream" in (rh.get("content-type") or ""):
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    d = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if d.get("id") == payload.get("id"):
                    msg = d
        if msg is None:
            raise RuntimeError("no JSON-RPC reply in SSE stream")
    else:
        msg = json.loads(raw)
    if "error" in msg:
        raise RuntimeError("JSON-RPC error: " + json.dumps(msg["error"])[:300])
    return msg["result"]


def rpc(method, params=None):
    _state["id"] += 1
    p = {"jsonrpc": "2.0", "id": _state["id"], "method": method}
    if params is not None:
        p["params"] = params
    return _post(p)


def initialize():
    res = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "nulb-syfert-raw", "version": "1.1"}})
    _state["server_info"] = res.get("serverInfo")
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_reply=False)
    return res


def server_info():
    if _state["server_info"] is None:
        initialize()
    return _state["server_info"]


def tools():
    server_info()
    out, cur = [], None
    while True:
        res = rpc("tools/list", {"cursor": cur} if cur else {})
        out.extend(res.get("tools", []))
        cur = res.get("nextCursor")
        if not cur:
            return out


def call(name, args):
    """-> dict(tool, args, is_error, text, json). json is structuredContent, else the text parsed as JSON."""
    server_info()
    res = rpc("tools/call", {"name": name, "arguments": args})
    text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    js = res.get("structuredContent")
    if js is None:
        try:
            js = json.loads(text)
        except (ValueError, TypeError):
            js = None
    return {"tool": name, "args": args, "is_error": bool(res.get("isError")), "text": text, "json": js}

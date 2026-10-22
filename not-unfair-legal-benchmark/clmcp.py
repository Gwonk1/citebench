# CourtListener MCP client for the trap benchmark.
# Auth: Authorization: Token <token>, read from ~/projects/.secrets/courtlistener.key.
# The token is never printed. This client calls read tools only.
import json
import os
import urllib.error
import urllib.request

URL = "https://mcp.courtlistener.com/"
TOKEN_PATH = os.path.expanduser("~/projects/.secrets/courtlistener.key")
UA = "not-unfair-legal-benchmark/0.1 (read-only citation benchmark)"


def _token():
    return open(TOKEN_PATH).read().strip()


def call(method, params=None, req_id=1, timeout=90):
    payload = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        payload["id"] = req_id
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Token " + _token(),
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        status = e.code
    return status, raw


def tool_text(raw):
    """Return the text content of a tools/call SSE or JSON-RPC body."""
    blob = raw
    for line in raw.splitlines():
        if line.startswith("data: "):
            blob = line[6:]
            break
    msg = json.loads(blob)
    if "error" in msg:
        raise RuntimeError(json.dumps(msg["error"])[:500])
    result = msg.get("result") or {}
    if result.get("isError"):
        parts = []
        for block in result.get("content") or []:
            if block.get("type") == "text":
                parts.append(block.get("text") or "")
        raise RuntimeError("\n".join(parts)[:500] or "tool error")
    parts = []
    for block in result.get("content") or []:
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
    if parts:
        return "\n".join(parts)
    return json.dumps(result)


def _tool(name, arguments, timeout=90):
    status, raw = call(
        "tools/call",
        {"name": name, "arguments": arguments},
        timeout=timeout,
    )
    if status != 200:
        raise RuntimeError(f"HTTP {status}: {raw[:300]}")
    return tool_text(raw)


def analyze(text, timeout=90):
    return _tool("analyze_citations", {"text": text}, timeout=timeout)


def get_item(endpoint_id, item_id, fields=None, timeout=90):
    args = {"endpoint_id": endpoint_id, "item_id": item_id}
    if fields:
        args["fields"] = fields
    return _tool("get_endpoint_item", args, timeout=timeout)


def health():
    req = urllib.request.Request(
        "https://mcp.courtlistener.com/health",
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

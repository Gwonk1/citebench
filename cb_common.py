# usage: imported by run.py / grade.py / report.py (not run directly)
"""citebench shared helpers: keys, results.db, price table, Syfert MCP client."""
import json
import os
import re
import sqlite3
import threading
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS_PATH = os.path.join(ROOT, "keys.env")
DB_PATH = os.path.join(ROOT, "results", "results.db")
MODELS_PATH = os.path.join(ROOT, "models.json")
MCP_URL = "https://mcp.syfert.com/mcp"

# Owner token has no per-minute cap, but be polite: <= 4 in-flight MCP requests process-wide.
MCP_SEMAPHORE = threading.BoundedSemaphore(4)


# ---------------------------------------------------------------- keys
def load_keys(path=KEYS_PATH):
    keys = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip().strip('"').strip("'")
    # environment overrides file (handy for CI); never printed anywhere
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID", "GEMINI_API_KEY",
              "SYFERT_MCP_TOKEN", "LOCAL_OPENAI_BASE"):
        if os.environ.get(k):
            keys[k] = os.environ[k]
    return keys


# ---------------------------------------------------------------- models / prices
def load_models(path=MODELS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- questions
def load_questions(path):
    qs = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                qs.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{n}: bad JSON: {e}")
    return qs


def default_questions_path():
    real = os.path.join(ROOT, "data", "questions.jsonl")
    if os.path.exists(real) and os.path.getsize(real) > 0:
        return real
    return os.path.join(ROOT, "data", "questions.sample.jsonl")


# ---------------------------------------------------------------- results.db
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, model TEXT, provider TEXT,
  arm TEXT CHECK(arm IN ('bare','mcp')), started_ts TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS answers(
  run_id TEXT, qid TEXT, raw_answer TEXT, tool_calls_json TEXT,
  tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL, latency_s REAL, error TEXT,
  PRIMARY KEY(run_id, qid));
CREATE TABLE IF NOT EXISTS grades(
  run_id TEXT, qid TEXT, n_cites INTEGER, n_verified INTEGER, n_fabricated INTEGER, n_unindexed INTEGER,
  n_name_mismatch INTEGER, n_quote_absent INTEGER, n_red INTEGER, n_yellow INTEGER,
  gold_hit INT, abstained INT, warned_treatment INT, grader_version TEXT, check_brief_json TEXT,
  n_quote_unattributed INTEGER, gold_equivalent INT, n_pin_reference INTEGER DEFAULT 0,
  PRIMARY KEY(run_id, qid));
"""


def open_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=30, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA_SQL)
    cols = {r[1] for r in con.execute("PRAGMA table_info(grades)")}
    for col, typ in (("warned_treatment", "INT"), ("n_unindexed", "INTEGER"), ("grader_version", "TEXT"),
                     ("n_quote_unattributed", "INTEGER"), ("gold_equivalent", "INT"),   # g7 (2026-09-23)
                     ("n_pin_reference", "INTEGER DEFAULT 0")):                         # g8 (2026-09-23)
        if col not in cols:  # DBs created before SCHEMA.md added the column
            con.execute(f"ALTER TABLE grades ADD COLUMN {col} {typ}")
            con.commit()
    return con


def load_gold(con, extra_paths=None):
    """qid -> question row, from the default question file, any --questions paths, and every
    question file a run in this DB was made from."""
    paths = list(extra_paths or []) or [default_questions_path()]
    for (cfg,) in con.execute("SELECT config_json FROM runs"):
        try:
            p = json.loads(cfg).get("questions")
        except Exception:
            p = None
        if p and p not in paths:
            paths.append(p)
    gold = {}
    for p in paths:
        if os.path.exists(p):
            for q in load_questions(p):
                gold.setdefault(q["id"], q)
    return gold


# ---------------------------------------------------------------- MCP client
class MCPError(Exception):
    pass


class MCPClient:
    """Minimal MCP streamable-HTTP client (JSON-RPC over POST). One per thread."""

    def __init__(self, token, url=MCP_URL, timeout=180):
        if not token:
            raise MCPError("SYFERT_MCP_TOKEN missing from keys.env")
        self.url = url
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "citebench/0.1",
        })
        self._id = 0
        self.session_id = None
        self.server_info = None
        self._tools = None

    def _post(self, payload, expect_reply=True):
        with MCP_SEMAPHORE:
            for attempt in range(3):
                try:
                    r = self.s.post(self.url, json=payload, timeout=self.timeout)
                except requests.RequestException as e:
                    if attempt == 2:
                        raise MCPError(f"network: {e}")
                    time.sleep(2 * (attempt + 1))
                    continue
                if r.status_code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
        if r.headers.get("mcp-session-id"):
            self.session_id = r.headers["mcp-session-id"]
            self.s.headers["Mcp-Session-Id"] = self.session_id
        if not expect_reply:
            return None
        if r.status_code != 200:
            raise MCPError(f"HTTP {r.status_code}: {r.text[:300]}")
        ctype = r.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            msg = None
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    try:
                        d = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if d.get("id") == payload.get("id"):
                        msg = d
            if msg is None:
                raise MCPError("no JSON-RPC reply in SSE stream")
        else:
            msg = r.json()
        if "error" in msg:
            raise MCPError(f"JSON-RPC error: {msg['error']}")
        return msg["result"]

    def _rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        return self._post(payload)

    def initialize(self):
        res = self._rpc("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "citebench", "version": "0.1"}})
        self.server_info = res.get("serverInfo")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_reply=False)
        return res

    def list_tools(self):
        if self._tools is None:
            if self.server_info is None:
                self.initialize()
            tools, cursor = [], None
            while True:
                res = self._rpc("tools/list", {"cursor": cursor} if cursor else {})
                tools.extend(res.get("tools", []))
                cursor = res.get("nextCursor")
                if not cursor:
                    break
            self._tools = tools
        return self._tools

    def call_tool(self, name, arguments):
        """Returns (text, is_error, structured_or_None)."""
        if self.server_info is None:
            self.initialize()
        res = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        parts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        return "\n".join(parts), bool(res.get("isError")), res.get("structuredContent")


# ---------------------------------------------------------------- citation normalisation
def norm_reporter(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


CITE_RE = re.compile(r"\b(\d{1,4})\s+([A-Z][A-Za-z0-9.'\s]{0,24}?)\s+(\d{1,5})\b")


def cite_keys(citation_text):
    """Set of (volume, normalized reporter, page) keys found in a bluebook string."""
    out = set()
    for v, rep, p in CITE_RE.findall(citation_text or ""):
        out.add((v, norm_reporter(rep), p))
    return out

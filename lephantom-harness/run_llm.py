#!/usr/bin/env python3
# usage: python3 run_llm.py --model claude-opus-5-5|local-gemma --arm bare|mcp --split pilot20|test|subset130 [--max-turns N] [--limit N] [--concurrency N] [--tag T] [--confirm-spend] [--max-usd X] [--thinking on|off] [--max-tokens N] [--tool-result-chars N] [--project 390]
"""LePhantomCite LLM arms.
bare = the paper's non-agentic prompt (repo max_steps=0 path), one call, no tools.
mcp  = tool loop with a trimmed set of Syfert MCP tools (lp_common.AGENTIC_SYSTEM); turn --max-turns is forced tool-free
       (tool_choice none + FINAL_INSTRUCTION) so every example ends with an answer.
Providers (raw HTTP, like ../run.py): anthropic (claude-opus-5-5: adaptive thinking is always on, output_config.effort
high, prompt caching via top-level cache_control; cost from models.json + cache prices below) and local (the llama-server
on :8097; <= 2 concurrent requests; before each request GET /slots and wait while slots we did not start are processing
(_foreign_busy, after syfertize/gcite_labels_runner.py); never starts a server).
Every model call is logged in results/lephantom.db (calls) with usage; per-example rows in preds (raw output, parsed
predictions, tool calls). Resumable (done ids skipped). Paid providers need --confirm-spend; --max-usd stops the run.
After the run prints measured tokens/example and the projected cost for --project examples (default 390)."""
import argparse, concurrent.futures as cf, datetime as dt, json, os, re, sys, threading, time
import urllib.request as ur
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cb_common import MCPClient, MCPError, load_keys, load_models
import lp_common as L
PROMPT_POLICY = "v1"

LOCAL_BASE = "http://127.0.0.1:8097/v1"
SLOTS_URL = "http://127.0.0.1:8097/slots"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
HTTP_TIMEOUT = 600
CACHE_PRICES = {"claude-opus-5-5": {"read": 0.20, "write": 5.0}}   # USD / 1M tokens (claude-api skill, 2026-10)
OPUS_TOOLS = ["check_brief", "check_citation", "verify_quote", "get_case", "search_cases", "find_case",
              "get_propositions", "search_quotes"]
def opus_tools():   # MCP98_20261020: --prompt v4 also allows context_detector (v1-v3 arms keep the list above)
    return OPUS_TOOLS + (["context_detector"] if PROMPT_POLICY == "v4" else [])

# MCPPROFILE_20261027: which MCP server the `mcp` arm talks to (Claude Code provider). Default = Syfert, byte-identical to the
# runs before this option existed. A profile JSON {"name": "<server key in mcp_config>", "mcp_config": "<path to a Claude Code
# mcp.json holding that one server>", "tools": [..tool names..], "tools_v4_extra": [..], "tool_policy_file": "<text file>"} lets
# another MCP run through the same prompts, matcher and scorer: tool names become mcp__<name>__<tool>, and the tool-policy block of
# the agentic system prompt is replaced by the file's text (the v2-v4 extras describe Syfert check_brief fields, so a foreign
# profile should run --prompt v1 unless it writes its own). Nothing in a profile is secret; the mcp.json it points at may hold a token
# and is never copied.
MCP_PROFILE = None
def load_mcp_profile(path):
    global MCP_PROFILE
    if not path:
        MCP_PROFILE = None
        return None
    prof = json.load(open(path))
    for k in ("name", "mcp_config", "tools"):
        if k not in prof:
            raise SystemExit(f"mcp profile {path}: missing {k}")
    prof["mcp_config"] = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(path)), prof["mcp_config"]))
    if not os.path.exists(prof["mcp_config"]):
        raise SystemExit(f"mcp profile: {prof['mcp_config']} missing (write your own Claude Code mcp.json; it is never copied)")
    if prof.get("tool_policy_file"):
        pf = os.path.join(os.path.dirname(os.path.abspath(path)), prof["tool_policy_file"])
        L.TOOL_POLICY_OVERRIDE = open(pf, encoding="utf-8").read()
    MCP_PROFILE = prof
    return prof
def mcp_server_name():
    return MCP_PROFILE["name"] if MCP_PROFILE else "syfert"
def mcp_tools():
    if MCP_PROFILE:
        return list(MCP_PROFILE["tools"]) + (list(MCP_PROFILE.get("tools_v4_extra") or []) if PROMPT_POLICY == "v4" else [])
    return opus_tools()
# 8k-context local model: 4 tools with short descriptions and the real (trimmed) schemas
GEMMA_TOOLS = {
    "check_citation": "Verify ONE case citation (e.g. '557 F.2d 170'). Says whether the case exists, its real name (compare with the name the brief gives), and checks a pinpoint page. Pass expected_case_name when the brief names the case.",
    "verify_quote": "Check whether a quotation appears verbatim in the cited opinion. Returns verdict and the opinion's own closest passage.",
    "get_case": "Read the opinion for a citation (text excerpt) to check what it actually holds and where quoted words sit.",
    "search_cases": "Find a case by party names or keywords when a citation does not resolve.",
}
GEMMA_PARAM_KEEP = {"check_citation": ["citation", "expected_case_name"], "verify_quote": ["quote", "citation"],
                    "get_case": ["citation", "query", "max_chars"], "search_cases": ["q", "query", "limit"]}


class ProviderError(Exception):
    pass


def _post(url, headers, body, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            last = f"network: {e}"; time.sleep(2 ** i); continue
        if r.status_code in (429, 500, 502, 503, 504, 529):
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            ra = r.headers.get("retry-after")
            time.sleep(float(ra) if ra and ra.replace('.', '', 1).isdigit() else 3 * 2 ** i); continue
        if r.status_code != 200:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:500]}")
        return r.json()
    raise ProviderError(last or "request failed")


# ---------------------------------------------------------------- local slot yield (gcite_labels_runner._foreign_busy)
_mine = [0]
_mine_lock = threading.Lock()
_last_foreign = [0.0]
YIELD_COOLDOWN = 2.0


def _foreign_busy():
    try:
        with ur.urlopen(SLOTS_URL, timeout=2) as r:
            busy = sum(1 for sl in json.load(r) if sl.get("is_processing"))
    except Exception:
        return False
    with _mine_lock:
        foreign = busy > _mine[0]
    if foreign:
        _last_foreign[0] = time.time()
    return foreign


MAX_YIELD = 8.0    # a librarian router call answers in a few seconds; foreign load that never clears is the yielding batch labeler (GCL21)


def wait_for_quiet(log):
    """Hold the request while slots we did not start are processing (librarian traffic first). Capped at MAX_YIELD s:
    the G-Cite label runner shares this server and itself yields to foreign traffic, so two polite yielders would
    otherwise wait on each other forever; once we start, it pauses for us."""
    t0 = None
    while _foreign_busy() or time.time() - _last_foreign[0] < YIELD_COOLDOWN:
        if t0 is None:
            t0 = time.time()
        if time.time() - t0 > MAX_YIELD:
            log["yield_capped"] = log.get("yield_capped", 0) + 1
            break
        time.sleep(1.0)
    if t0 is not None:
        log["yield_s"] = log.get("yield_s", 0) + round(time.time() - t0, 1)


# ---------------------------------------------------------------- providers
class Anthropic:
    def __init__(self, key, workspace, model, prices, max_tokens, effort="high"):
        self.key, self.ws, self.model, self.prices, self.max_tokens, self.effort = key, workspace, model, prices, max_tokens, effort

    def tools_fmt(self, mcp_tools):
        return [{"name": t["name"], "description": t.get("description", ""),
                 "input_schema": t.get("inputSchema") or {"type": "object", "properties": {}}} for t in mcp_tools]

    def new(self, system, user):
        return {"system": system, "messages": [{"role": "user", "content": user}]}

    def step(self, st, tools, allow_tools):
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": st["messages"],
                "system": st["system"], "output_config": {"effort": self.effort}}
        if tools:   # caching pays only in the tool loop (the prefix is re-sent every turn); bare arm = one call
            body["cache_control"] = {"type": "ephemeral"}
            body["tools"] = tools
            body["tool_choice"] = {"type": "auto" if allow_tools else "none"}
        h = {"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self.ws:
            h["anthropic-workspace-id"] = self.ws
        d = _post(ANTHROPIC_URL, h, body)
        if d.get("stop_reason") == "refusal":
            raise ProviderError(f"refusal: {json.dumps(d.get('stop_details'))[:300]}")
        content = d.get("content", [])
        st["messages"].append({"role": "assistant", "content": content})   # verbatim (thinking blocks + signatures)
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        calls = [(b["id"], b["name"], b.get("input") or {}) for b in content if b.get("type") == "tool_use"]
        u = d.get("usage") or {}
        usage = {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
                 "cache_read": u.get("cache_read_input_tokens", 0) or 0, "cache_write": u.get("cache_creation_input_tokens", 0) or 0,
                 "stop": d.get("stop_reason")}
        usage["cost"] = (usage["in"] * self.prices["in"] + usage["out"] * self.prices["out"]
                         + usage["cache_read"] * self.prices["cache_read"] + usage["cache_write"] * self.prices["cache_write"]) / 1e6
        return text, calls, usage

    def add_results(self, st, calls, results):
        st["messages"].append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": res} for (cid, _, _), res in zip(calls, results)]})

    def add_user(self, st, text):
        last = st["messages"][-1]
        if last["role"] == "user" and isinstance(last["content"], list):
            last["content"].append({"type": "text", "text": text})
        else:
            st["messages"].append({"role": "user", "content": text})


class Local:
    """llama-server OpenAI-compatible endpoint; thinking via chat_template_kwargs; reasoning split out (reasoning_format)."""

    def __init__(self, model, max_tokens, thinking, n_ctx=8192):
        self.model, self.max_tokens, self.thinking, self.n_ctx = model, max_tokens, thinking, n_ctx

    def tools_fmt(self, mcp_tools):
        out = []
        for t in mcp_tools:
            if t["name"] not in GEMMA_TOOLS:
                continue
            schema = json.loads(json.dumps(t.get("inputSchema") or {"type": "object", "properties": {}}))
            keep = GEMMA_PARAM_KEEP[t["name"]]
            props = {k: v for k, v in (schema.get("properties") or {}).items() if k in keep}
            for v in props.values():
                if isinstance(v.get("description"), str):
                    v["description"] = v["description"][:160]
            schema["properties"] = props
            schema["required"] = [r for r in (schema.get("required") or []) if r in props]
            out.append({"type": "function", "function": {"name": t["name"], "description": GEMMA_TOOLS[t["name"]], "parameters": schema}})
        return out

    def new(self, system, user):
        return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "log": {}}

    def step(self, st, tools, allow_tools):
        body = {"model": self.model, "messages": st["messages"], "max_tokens": self.max_tokens,
                "chat_template_kwargs": {"enable_thinking": bool(self.thinking)}, "reasoning_format": "deepseek"}
        if tools:
            body["tools"] = tools
            # turn 1 of the agentic arm must be a tool call (E4B otherwise answers from memory and never uses a tool;
            # the paper's harness likewise starts every episode with an action)
            body["tool_choice"] = "auto" if allow_tools else "none"   # "required" is not honoured by this server (text loops)
        with _mine_lock:
            _mine[0] += 1
        try:
            # yield to the librarian's own traffic (we already counted ourselves in _mine)
            with _mine_lock:
                _mine[0] -= 1
            wait_for_quiet(st["log"])
            with _mine_lock:
                _mine[0] += 1
            d = _post(LOCAL_BASE + "/chat/completions", {"Content-Type": "application/json"}, body, tries=3)
        finally:
            with _mine_lock:
                _mine[0] -= 1
        if "choices" not in d or not d["choices"]:
            raise ProviderError(f"no choices: {json.dumps(d)[:300]}")
        ch = d["choices"][0]
        msg = ch["message"]
        st["messages"].append({k: v for k, v in msg.items() if v is not None and k != "reasoning_content"})
        calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_unparseable": tc["function"].get("arguments")}
            calls.append((tc.get("id") or f"call_{len(calls)}", tc["function"]["name"], args))
        u = d.get("usage") or {}
        usage = {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0), "cache_read": 0, "cache_write": 0,
                 "cost": 0.0, "stop": ch.get("finish_reason"), "reasoning_chars": len(msg.get("reasoning_content") or "")}
        return (msg.get("content") or ""), calls, usage

    def add_results(self, st, calls, results):
        for (cid, name, _), res in zip(calls, results):
            st["messages"].append({"role": "tool", "tool_call_id": cid, "name": name, "content": res})

    def add_user(self, st, text):
        st["messages"].append({"role": "user", "content": text})


# ---------------------------------------------------------------- Claude Code harness (subscription)
class ClaudeCode:
    """One example = one headless `claude -p` subprocess (Claude Code's own harness, SUBSCRIPTION/OAuth auth: every API
    key scrubbed from its environment). Ported from ../run.py ClaudeCode. mcp arm: ONLY the Syfert MCP
    (--strict-mcp-config + ../.ccrun/mcp.json, which carries the bench token and is never copied), built-in tools removed
    (--tools ""), the 8 bench tools pre-approved by exact name. bare arm: empty MCP config, no tools. Clean cwd .ccrun/,
    --setting-sources "" (no user/project settings, hooks, CLAUDE.md), --no-session-persistence. Not 1:1 with a raw
    API loop: Claude Code adds its own system prompt and turn handling; cost = nominal total_cost_usd (subscription)."""
    CWD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".ccrun")
    SCRUB = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "OPENROUTER_API_KEY",
             "GEMINI_API_KEY", "SYFERT_MCP_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")

    def __init__(self, model, arm, max_turns, timeout=1500, effort=None):
        self.model, self.arm, self.max_turns, self.timeout = model, arm, max_turns, timeout
        self.effort = effort   # 2026-10-19: optional `claude --effort <level>` passthrough (harness setting, disclosed)
        self.max_tokens = None
        self.mcp = os.path.join(self.CWD, "mcp.json" if arm == "mcp" else "mcp_empty.json")
        if arm == "mcp" and MCP_PROFILE:
            self.mcp = MCP_PROFILE["mcp_config"]   # MCPPROFILE_20261027
        if not os.path.exists(self.mcp):
            raise SystemExit(f"claudecode: {self.mcp} missing")
        self.prices = {"note": "subscription; nominal total_cost_usd from claude -p"}

    def argv(self, system, prompt):
        a = ["claude", "-p", prompt, "--model", self.model, "--strict-mcp-config", "--mcp-config", self.mcp,
             "--tools", "", "--setting-sources", "", "--no-session-persistence", "--system-prompt", system,
             "--max-turns", str(self.max_turns), "--output-format", "stream-json", "--verbose"]
        if self.arm == "mcp":
            a += ["--allowedTools", ",".join(f"mcp__{mcp_server_name()}__{t}" for t in mcp_tools())]
        if self.effort:
            a += ["--effort", self.effort]
        return a

    def run(self, system, prompt):
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in self.SCRUB}
        t0 = time.time()
        try:
            p = subprocess.run(self.argv(system, prompt), cwd=self.CWD, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return {"text": None, "tools": [], "in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0,
                    "turns": 0, "error": f"timeout {self.timeout}s", "meta": {}}
        tools, init, result, pending = [], None, None, {}
        for line in p.stdout.splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "system" and d.get("subtype") == "init":
                init = d
            elif d.get("type") == "assistant":
                for b in (d.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_use":
                        rec = {"turn": len(tools) + 1, "name": b.get("name"), "args": b.get("input")}
                        pending[b.get("id")] = rec
                        tools.append(rec)
            elif d.get("type") == "user":
                for b in (d.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                        c = b.get("content")
                        txt = c if isinstance(c, str) else "".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                        pending[b["tool_use_id"]].update(is_error=bool(b.get("is_error")), result_chars=len(txt))
            elif d.get("type") == "result":
                result = d
        if not result:
            return {"text": None, "tools": tools, "in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0,
                    "turns": 0, "error": f"claude exit {p.returncode}: {(p.stderr or '')[-300:]}", "meta": {}}
        u = result.get("usage") or {}
        err = None
        if result.get("is_error") or result.get("subtype") != "success":
            err = f"{result.get('subtype')}: {str(result.get('result') or result.get('api_error_status'))[:200]}"
        elif not (result.get("result") or "").strip():
            err = "empty final answer"
        meta = {"num_turns": result.get("num_turns"), "nominal_cost_usd": result.get("total_cost_usd"),
                "permission_denials": result.get("permission_denials"), "duration_ms": result.get("duration_ms"),
                "terminal_reason": result.get("terminal_reason"), "tools_offered": (init or {}).get("tools"),
                "apiKeySource": (init or {}).get("apiKeySource"), "model_served": list((result.get("modelUsage") or {}).keys())}
        return {"text": result.get("result"), "tools": tools, "in": u.get("input_tokens") or 0, "out": u.get("output_tokens") or 0,
                "cache_read": u.get("cache_read_input_tokens") or 0, "cache_write": u.get("cache_creation_input_tokens") or 0,
                "cost": float(result.get("total_cost_usd") or 0.0), "turns": result.get("num_turns") or 0, "error": err, "meta": meta}


def run_example_cc(r, arm, prov, con, run_id, lock):
    t0 = time.time()
    system, user = L.nonagentic_messages(r["text"]) if arm == "bare" else L.agentic_messages(r["text"], PROMPT_POLICY)
    out = prov.run(system, user)
    text, err = out["text"], out["error"]
    preds, status = L.parse_predictions(text) if text else ([], "none")
    if not err and status in ("unparsed", "none"):
        err = f"unparsed output ({status})"
    tool_log = out["tools"] + [{"name": "_claudecode", **out["meta"]}]
    tot = {k: out[k] for k in ("in", "out", "cache_read", "cache_write", "cost")}
    with lock:
        con.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, r["id"], out["turns"], "claude-p", prov.model, tot["in"], tot["out"], tot["cache_read"], tot["cache_write"],
                     tot["cost"], round(time.time() - t0, 2), dt.datetime.now().isoformat(timespec="seconds")))
        con.execute("INSERT OR REPLACE INTO preds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, r["id"], json.dumps(preds, ensure_ascii=False), text, status, json.dumps(tool_log, ensure_ascii=False),
                     out["turns"], tot["in"], tot["out"], tot["cache_read"], tot["cache_write"], round(tot["cost"], 6),
                     round(time.time() - t0, 2), err, dt.datetime.now().isoformat(timespec="seconds")))
        con.commit()
    return r["id"], err, len(preds), tot, out["turns"], len(out["tools"])


# ---------------------------------------------------------------- one example
def run_example(r, arm, prov, tools, keys, max_turns, tls, tool_result_chars, con, run_id, lock, ctx_guard=None):
    t0 = time.time()
    if arm == "bare":
        system, user = L.nonagentic_messages(r["text"])
    else:
        system, user = L.agentic_messages(r["text"], PROMPT_POLICY)
    st = prov.new(system, user)
    tot = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0}
    tool_log, err, text, turns = [], None, "", 0
    try:
        for turn in range(1, (1 if arm == "bare" else max_turns) + 1):
            turns = turn
            allow = arm == "mcp" and turn < max_turns
            if arm == "mcp" and not allow:
                prov.add_user(st, L.FINAL_INSTRUCTION)
            t1 = time.time()
            text, calls, u = prov.step(st, tools if arm == "mcp" else None, allow)
            for k in tot:
                tot[k] += u.get(k, 0) or 0
            with lock:
                con.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (run_id, r["id"], turn, "model", prov.model, u["in"], u["out"], u["cache_read"], u["cache_write"],
                             u["cost"], round(time.time() - t1, 2), dt.datetime.now().isoformat(timespec="seconds")))
                con.commit()
            if u.get("stop") in ("max_tokens", "length"):
                tool_log.append({"turn": turn, "name": "_truncated", "stop": u["stop"]})
            if not calls and arm == "mcp" and turn == 1 and isinstance(prov, Local) and not st.get("nudged"):
                # E4B tends to answer from memory on turn 1; the paper's harness starts every episode with an action, so give
                # one nudge (the un-tooled answer is dropped) and let it try again. Logged; a second refusal is accepted.
                st["nudged"] = True
                st["messages"].pop()
                prov.add_user(st, L.TOOL_NUDGE)
                tool_log.append({"turn": turn, "name": "_tool_nudge"})
                continue
            if not calls or arm == "bare":
                break
            results = []
            for cid, name, args in calls:
                t2 = time.time()
                if not hasattr(tls, "mcp"):
                    tls.mcp = MCPClient(keys.get("SYFERT_MCP_TOKEN"), timeout=300)
                try:
                    res, is_err, _ = tls.mcp.call_tool(name, args)
                except MCPError as e:
                    res, is_err = f"tool error: {e}", True
                full = len(res)
                if full > tool_result_chars:
                    res = res[:tool_result_chars] + f"\n...[truncated {full - tool_result_chars} chars]"
                tool_log.append({"turn": turn, "name": name, "args": args, "is_error": is_err, "result_chars": full,
                                 "fed_chars": len(res), "latency_s": round(time.time() - t2, 2)})
                results.append(res)
            if ctx_guard:
                # 8k-context guard for the local model: keep prompt + max_tokens inside n_ctx (shrink this turn's results to
                # fit) and force the final answer when the prompt is getting full
                budget = prov.n_ctx - prov.max_tokens - 400 - u["in"] - u["out"]   # tokens left for these results (+ the final nudge)
                est = sum(len(x) // 3 for x in results)
                if est > max(budget, 0):
                    per = max(200, int(budget * 3 / max(len(results), 1)))
                    results = [x[:per] + "\n...[cut to fit context]" if len(x) > per else x for x in results]
                    tool_log.append({"turn": turn, "name": "_ctx_shrink", "prompt_tokens": u["in"], "per_result_chars": per})
                if u["in"] + sum(len(x) // 3 for x in results) > ctx_guard and turn < max_turns - 1:
                    max_turns = turn + 1
                    tool_log.append({"turn": turn, "name": "_ctx_guard", "prompt_tokens": u["in"]})
            prov.add_results(st, calls, results)
        if arm == "mcp" and isinstance(prov, Local) and (calls or L.parse_predictions(text)[1] in ("unparsed", "none")):
            # the forced tool-free turn gave a tool call, nothing, or prose: one more plain-text turn (run.py's TOOLS_CLOSED nudge)
            tool_log.append({"turn": turns, "name": "_final_retry", "had_calls": bool(calls), "text_chars": len(text or "")})
            prov.add_user(st, "Answer now with the JSON array of hallucinated segments only (use [] if none). No tool calls.")
            text2, calls2, u2 = prov.step(st, None, False)
            for k in tot:
                tot[k] += u2.get(k, 0) or 0
            with lock:
                con.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (run_id, r["id"], turns + 1, "model", prov.model, u2["in"], u2["out"], 0, 0, 0.0, 0.0,
                             dt.datetime.now().isoformat(timespec="seconds")))
                con.commit()
            if (text2 or "").strip():
                text, calls = text2, calls2
        if calls and arm == "mcp" and not (text or "").strip():
            err = "final turn was a tool call (no answer)"
    except ProviderError as e:
        err = str(e)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:500]
    preds, status = L.parse_predictions(text) if text else ([], "none")
    if not err and status in ("unparsed", "none"):
        err = f"unparsed output ({status})"
    if isinstance(st, dict) and st.get("log", {}).get("yield_s"):
        tool_log.append({"name": "_yield", "seconds": st["log"]["yield_s"], "capped": st["log"].get("yield_capped", 0)})
    with lock:
        con.execute("INSERT OR REPLACE INTO preds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, r["id"], json.dumps(preds, ensure_ascii=False), text, status, json.dumps(tool_log, ensure_ascii=False),
                     turns, tot["in"], tot["out"], tot["cache_read"], tot["cache_write"], round(tot["cost"], 6),
                     round(time.time() - t0, 2), err, dt.datetime.now().isoformat(timespec="seconds")))
        con.commit()
    return r["id"], err, len(preds), tot, turns, len([t for t in tool_log if not t["name"].startswith("_")])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--arm", choices=["bare", "mcp"], required=True)
    ap.add_argument("--split", default="pilot20")
    ap.add_argument("--max-turns", type=int)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--max-usd", type=float)
    ap.add_argument("--thinking", choices=["on", "off"], default="on")
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--tool-result-chars", type=int)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--cc-effort", choices=("low", "medium", "high", "xhigh", "max"), help="claudecode provider only: pass `claude --effort <level>` (default: Claude Code's own default)")
    ap.add_argument("--prompt", choices=("v1", "v2", "v3", "v4"), default="v1", help="agentic tool policy: v1 = original; v2 = + verdict table / copy-exactly (lp_common.AGENTIC_POLICY_V2); v3 = + V3_EXTRA; v4 = v3 + context_detector (AGENTIC_POLICY_V4_EXTRA, MCP98_20261020)")
    ap.add_argument("--project", type=int, default=390)
    ap.add_argument("--mcp-profile", help="MCPPROFILE_20261027: JSON profile of another MCP server for the mcp arm (Claude Code provider only); default = Syfert, unchanged")
    a = ap.parse_args()
    global PROMPT_POLICY
    PROMPT_POLICY = a.prompt
    load_mcp_profile(a.mcp_profile)
    if a.mcp_profile and a.arm == "mcp" and a.prompt != "v1" and not (MCP_PROFILE.get("tool_policy_file")):
        raise SystemExit("--mcp-profile with --prompt v2-v4 needs a tool_policy_file: the v2-v4 extras describe Syfert check_brief fields")
    keys = load_keys()
    models = load_models()["models"]
    models["claudecode-opus"] = {"provider": "claudecode", "model": "claude-opus-5-5", "in_per_m": 0, "out_per_m": 0,
                                 "note": "Claude Code harness, subscription (OAuth); nominal cost only"}
    models["claudecode-opus48"] = {"provider": "claudecode", "model": "claude-opus-4-8", "in_per_m": 0, "out_per_m": 0,
                                   "note": "Claude Code harness, subscription; the paper's model (Opus 4.8)"}
    models["claudecode-fable"] = {"provider": "claudecode", "model": "claude-fable-5-1", "in_per_m": 0, "out_per_m": 0,
                                  "note": "Claude Code harness, subscription; Fable 5.1 (final run after the tool fixes)"}
    spec = models[a.model]
    provider = spec["provider"]
    rows = L.load_split(a.split)[: a.limit or None]
    if provider == "anthropic":
        if not a.confirm_spend:
            raise SystemExit("paid provider: add --confirm-spend")
        cp = CACHE_PRICES.get(spec["model"], {"read": spec["in_per_m"] * 0.1, "write": spec["in_per_m"] * 1.25})
        prices = {"in": spec["in_per_m"], "out": spec["out_per_m"], "cache_read": cp["read"], "cache_write": cp["write"]}
        prov = Anthropic(keys["ANTHROPIC_API_KEY"], keys.get("ANTHROPIC_WORKSPACE_ID"), spec["model"], prices,
                         a.max_tokens or (16000 if a.arm == "bare" else 8000), a.effort)
        conc = min(4, a.concurrency or 4)
        tool_names, trc, ctx_guard = opus_tools(), a.tool_result_chars or 12000, None
    elif provider == "claudecode":
        prov = ClaudeCode(spec["model"], a.arm, a.max_turns or 30, effort=a.cc_effort)
        conc = min(6, a.concurrency or 3)   # cap raised 3 -> 6 on 2026-10-19 for the max-effort finals (watch for rate-limit errors)
        tool_names, trc, ctx_guard = mcp_tools(), None, None
    elif provider == "local":
        served = requests.get(LOCAL_BASE + "/models", timeout=5).json()["data"][0]["id"]
        prov = Local(served, a.max_tokens or 1500, a.thinking == "on")
        conc = min(2, a.concurrency or 2)
        tool_names, trc, ctx_guard = list(GEMMA_TOOLS), a.tool_result_chars or 1800, 5200
    else:
        raise SystemExit(f"provider {provider} not supported here")
    max_turns = a.max_turns or (30 if provider == "anthropic" else 15)
    tools = None
    if a.arm == "mcp" and provider != "claudecode":
        if MCP_PROFILE:
            raise SystemExit("--mcp-profile is supported by the claudecode provider only (the raw-API and local loops call the Syfert MCP directly)")
        mcp = MCPClient(keys.get("SYFERT_MCP_TOKEN"))
        raw = [t for t in mcp.list_tools() if t["name"] in tool_names]
        tools = prov.tools_fmt(raw)
    run_id = f"{a.model}:{a.arm}:{a.split}:{a.tag}"
    con = L.open_db()
    cfg = {"model": spec["model"], "provider": provider, "arm": a.arm, "split": a.split, "max_turns": max_turns, "prompt_policy": a.prompt, "cc_effort": a.cc_effort,
           "mcp_profile": ({k: v for k, v in MCP_PROFILE.items() if k != "mcp_config"} if MCP_PROFILE else "syfert (default)"),
           "max_tokens": prov.max_tokens, "thinking": (a.thinking if provider == "local" else "adaptive(always on)"),
           "harness": ("claude -p (Claude Code, subscription): " + " ".join(prov.argv("<system>", "<prompt>")) if provider == "claudecode" else "raw HTTP loop"),
           "effort": (a.effort if provider == "anthropic" else None), "tools": tool_names if a.arm == "mcp" else [],
           "tool_result_chars": trc, "ctx_guard": ctx_guard, "prices": (prov.prices if provider == "anthropic" else None),
           "system_prompt": (L.NONAGENTIC_SYSTEM if a.arm == "bare" else (L.AGENTIC_SYSTEM if L.TOOL_POLICY_OVERRIDE is None else L.AGENTIC_SYSTEM_HEAD + L.TOOL_POLICY_OVERRIDE)), "user_prompt": L.NONAGENTIC_USER,
           "response_requirements": L.RESPONSE_REQUIREMENTS, "domain_knowledge": (L.DOMAIN_KNOWLEDGE if a.arm == "mcp" else None),
           "tool_schemas_chars": len(json.dumps(tools)) if tools else 0}
    con.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?)", (run_id, a.arm, a.model, a.split,
                                                                 dt.datetime.now().isoformat(timespec="seconds"), json.dumps(cfg)))
    con.commit()
    done = L.done_ids(con, run_id)
    todo = [r for r in rows if r["id"] not in done]
    spent0 = con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM preds WHERE run_id=?", (run_id,)).fetchone()[0]
    print(f"{run_id}: {len(rows)} examples, {len(todo)} to do, concurrency {conc}, max_turns {max_turns}, "
          f"tool schema chars {cfg['tool_schemas_chars']}, spent so far ${spent0:.2f}", flush=True)
    tls = threading.local(); lock = threading.Lock()
    spent = [spent0]; stop = [False]

    def work(r):
        if stop[0]:
            return r["id"], "skipped: --max-usd reached", 0, {"cost": 0, "in": 0, "out": 0, "cache_read": 0, "cache_write": 0}, 0, 0
        if provider == "claudecode":
            out = run_example_cc(r, a.arm, prov, con, run_id, lock)
        else:
            out = run_example(r, a.arm, prov, tools, keys, max_turns, tls, trc, con, run_id, lock, ctx_guard)
        with lock:
            spent[0] += out[3]["cost"]
            if a.max_usd and spent[0] >= a.max_usd:
                stop[0] = True
        return out

    n = 0; t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        for ex_id, err, npred, tot, turns, ncalls in ex.map(work, todo):
            n += 1
            print(f"[{n}/{len(todo)}] {ex_id} preds={npred} turns={turns} tools={ncalls} in={tot['in']} out={tot['out']} "
                  f"cr={tot['cache_read']} cw={tot['cache_write']} ${tot['cost']:.3f} total=${spent[0]:.2f} {err or ''}", flush=True)
    # summary + projection
    q = con.execute("SELECT COUNT(*), SUM(tokens_in), SUM(tokens_out), SUM(cache_read), SUM(cache_write), SUM(cost_usd), "
                    "SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END), AVG(n_turns), AVG(latency_s) FROM preds WHERE run_id=?", (run_id,)).fetchone()
    cnt = q[0] or 1
    print(f"SUMMARY {run_id}: n={q[0]} errors={q[6]} avg_turns={q[7]:.1f} avg_latency={q[8]:.0f}s "
          f"tokens/example in={q[1] / cnt:.0f} out={q[2] / cnt:.0f} cache_read={q[3] / cnt:.0f} cache_write={q[4] / cnt:.0f} "
          f"cost/example=${q[5] / cnt:.4f} total=${q[5]:.2f} elapsed={time.time() - t0:.0f}s")
    print(f"PROJECTION for {a.project} examples: ${q[5] / cnt * a.project:.2f}")


if __name__ == "__main__":
    main()

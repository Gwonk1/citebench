#!/usr/bin/env python3
# usage: python3 run.py --model <key from models.json> --arm bare|mcp [--self-check] [--questions FILE] [--limit N] [--dry-run] [--confirm-spend] [--max-usd X] [--concurrency N] [--tag T] [--tool-result-chars N] [--db PATH]
"""Run one (model, arm) over the citebench question set and store answers in results/results.db.

bare = one chat call with the prompt.
mcp  = tool-use loop (max --max-turns model turns) with the Syfert MCP tools; the last turn is
       forced tool-free so every question ends with an answer.
mcp --self-check = after the final answer the HARNESS sends it to check_brief itself; if check_brief reports a
       misquote / quote absent from the cited opinion, an unresolved or name-mismatched cite, or a red-flagged
       case, the model gets ONE more user turn with the findings (SELF_CHECK_PROMPT) and revises with its normal
       tools (--max-turns covers the whole question; if the draft used every turn, the revision still gets one
       tool-free turn, logged as over_budget_turn). A clean check leaves the draft as the answer. arm stays 'mcp'
       in results.db; run_id = <model>:mcp:<tag>+check; config_json.self_check = true. The check is logged in
       tool_calls_json as a pseudo-call {"name": "_self_check", ...} (draft, findings, revised, revision tokens);
       the revision's tokens/cost are in the answer's totals. claudecode: sessions are not persisted
       (--no-session-persistence), so the revision is a FRESH `claude -p` whose prompt carries the question, the
       draft and the findings, with the turns the draft left over.
--tool-result-chars N (default: models.json "tool_result_chars" for the model, else 12000) truncates each tool
       result fed back to the model; recorded in config_json, and a run_id cannot be resumed with a different value.
Resumable: (run_id, qid) pairs with a stored non-error answer are skipped; errored ones retried.
Tool-call leaks: a final answer that is (or begins with) a tool call written as text ("<|tool_call>call:get_case{...}
       <tool_call|>", <tool_call>{json}</tool_call>, bare {"name", "arguments"} JSON, ...; tool_call_leak()) is stored
       as error "tool_call_leak" with raw_answer NULL, so the next invocation retries it. local provider only: when the
       forced tool-free turn still yields a tool call (text or parsed), that turn is dropped and the model gets ONE more
       tool-free turn after the user nudge TOOLS_CLOSED_NUDGE; logged as a {"name": "_tool_call_leak"} pseudo-call.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import re
import sys
import threading
import time

import requests

from cb_common import (ROOT, MCPClient, MCPError, default_questions_path, load_keys,
                       load_models, load_questions, open_db)

BARE_SYSTEM = None  # bare arm sends the prompt alone, exactly as written in questions.jsonl
MCP_SYSTEM = ("You have access to legal research tools backed by a database of U.S. case law and statutes. "
              "Use them to find and verify authority before you answer. When you are done researching, "
              "give your final answer as plain text.")
DEFAULT_TOOL_RESULT_CHARS = 12000   # tool output fed back to the model is truncated to this (recorded per call)
HTTP_TIMEOUT = 300
SELF_CHECK_PROMPT = ("Your draft was checked against the case-law database. Findings: {findings}. Revise your "
                     "answer; replace any misquoted passage with the verbatim text, drop or fix any citation that "
                     "did not resolve, and note any red-flagged case. Return the full revised answer as plain text.")
# claudecode revision = a fresh process (no persisted session to --resume), so the prompt carries everything
CC_REVISE_PROMPT = ("{question}\n\n---\nYou already drafted this answer:\n\n{draft}\n\n---\n" + SELF_CHECK_PROMPT)


def strip_md(t):
    """Mirror of grade.strip_md, so check_brief sees the same text the grader sends."""
    t = re.sub(r"^[ \t]{0,3}(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+)", "", t or "", flags=re.M)
    t = re.sub(r"\*(?!\d)", "", t)
    t = re.sub(r"(?<![A-Za-z0-9])_{1,3}(?=\S)(.+?)(?<=\S)_{1,3}(?![A-Za-z0-9])", r"\1", t)
    return t.replace("`", "")


def brief_findings(body, cap=20, snip=600):
    """check_brief body -> the problems the self-check reports back to the model ([] = the draft stands).
    Case cites only: unresolved, party-name mismatch, quote not verbatim in the cited opinion, red flag."""
    out, seen = [], set()

    def add(f):
        k = (f.get("cite"), f["problem"], f.get("quote"))
        if k not in seen and len(out) < cap:
            seen.add(k)
            out.append(f)

    for c in body.get("cites") or []:
        raw = c.get("raw")
        pc = c.get("party_check") or {}
        name = pc.get("resolved_name") or (c.get("case") or {}).get("case_name")
        if c.get("cluster_id") is None:
            f = {"cite": raw, "problem": "citation did not resolve to any case"}
            dym = [f"{d.get('case_name')}, {c.get('volume')} {c.get('reporter')} {d.get('page')} ({d.get('year')})"
                   for d in (c.get("did_you_mean") or [])[:3]]
            if dym:
                f["did_you_mean"] = dym
            add(f)
            continue
        if pc.get("verdict") == "mismatch":
            cl = pc.get("claimed") or c.get("claimed") or {}
            add({"cite": raw, "problem": "case name does not match the citation",
                 "you_wrote": " v. ".join(x for x in (cl.get("lhs"), cl.get("rhs")) if x), "cite_is": name})
        for qc in c.get("quote_checks") or ([c["quote_check"]] if c.get("quote_check") else []):
            if qc.get("integrity") == "absent" or qc.get("verdict") in ("misquote", "paraphrase"):
                bm = qc.get("best_match")
                add({"cite": raw, "case": name,
                     "problem": ("quoted words are a paraphrase, not verbatim" if qc.get("verdict") == "paraphrase"
                                 else "misquote: not verbatim in the cited opinion"),
                     "quote": (qc.get("brief_quote") or "")[:snip],
                     "best_match": bm[:snip] if bm else "(no matching passage found in this opinion)",
                     "match_percent": qc.get("percent")})
        if (c.get("treatment") or {}).get("flag_color") == "red":
            ob = c.get("overruled_by") or {}
            f = {"cite": raw, "case": name, "problem": "red flag: overruled or no longer good law"}
            if ob.get("overruler_name"):
                f["overruled_by"] = (f"{ob.get('verb') or 'overruled'} by {ob['overruler_name']} "
                                     f"({(ob.get('overruler_date') or '')[:4]})")
            add(f)
    return out


def mock_check_body(q):
    """--dry-run stand-in for check_brief: odd question numbers get one misquote, even ones come back clean."""
    digits = "".join(ch for ch in q["id"] if ch.isdigit())
    if not digits or int(digits) % 2 == 0:
        return {"mode": "mock", "stats": {"extracted": 1, "resolved": 1, "unresolved": 0}, "cites": []}
    return {"mode": "mock", "stats": {"extracted": 1, "resolved": 1, "unresolved": 0, "misquote": 1}, "cites": [
        {"raw": q.get("gold_citation"), "cluster_id": 1, "treatment": {"flag_color": "green"},
         "party_check": {"verdict": "match", "resolved_name": q.get("gold_case_name")},
         "quote_checks": [{"brief_quote": "the mock quoted words", "best_match": "the mock verbatim words",
                           "percent": 71, "verdict": "misquote", "integrity": "absent"}]}]}


def run_self_check(text, q, keys, tls, dry):
    """Harness-side check_brief on a draft answer -> (findings, the _self_check log record)."""
    t1 = time.time()
    sent = strip_md(text)
    info = {"name": "_self_check", "args": {"tool": "check_brief", "text_chars": len(sent)}, "draft": text}
    try:
        if dry:
            body = mock_check_body(q)
        else:
            if not hasattr(tls, "mcp"):
                tls.mcp = MCPClient(keys.get("SYFERT_MCP_TOKEN"))
            res, is_err, structured = tls.mcp.call_tool("check_brief", {"text": sent})
            if is_err:
                raise MCPError(f"check_brief isError: {res[:200]}")
            body = structured or json.loads(res)
        findings = brief_findings(body)
        info.update(is_error=False, stats=body.get("stats"), findings=findings)
    except Exception as e:  # a failed check never costs the answer: the draft stands
        findings = []
        info.update(is_error=True, error=f"{type(e).__name__}: {e}"[:300], findings=[])
    info["latency_s"] = round(time.time() - t1, 2)
    info["revised"] = False
    return findings, info


def findings_json(findings):
    return json.dumps(findings, ensure_ascii=False, separators=(",", ":"))


class ProviderError(Exception):
    pass


# A final answer that IS (or begins with) a tool call written as text. Gemma 4 on llama.cpp emits
# "<|tool_call>call:get_case{cluster_id:1354880,...}<tool_call|>" on the forced tool-free turn (tool_choice "none"
# switches the server's tool-call parser off, so the block arrives as content). Also the other text shapes llama.cpp's
# parsers read: Hermes/Qwen <tool_call>{json}</tool_call>, Mistral [TOOL_CALLS], Llama 3 <|python_tag|>, functionary
# <function=...>, and bare JSON {"name", "arguments"|"parameters"} / {"tool_call(s)": ...} / {"function": {...}}.
TOOL_LEAK_ERROR = "tool_call_leak"
TOOLS_CLOSED_NUDGE = "Tools are closed. Write your final answer as plain text."
TOOL_LEAK_RE = re.compile(r"^\s*(?:<\|tool_call\|?>|<tool_call>|\[TOOL_CALLS\]|<\|python_tag\|>|<function[=>]|"
                          r"call:[A-Za-z_]\w*\s*\{)")


def tool_call_leak(text):
    """True when the answer consists of / begins with a tool-call block instead of prose."""
    t = (text or "").strip()
    if not t:
        return False
    if TOOL_LEAK_RE.match(t):
        return True
    t = re.sub(r"^```(?:json)?\s*", "", t)
    if t[:1] not in "{[":
        return False
    try:
        obj, _ = json.JSONDecoder().raw_decode(t)
    except ValueError:
        return False
    items = obj if isinstance(obj, list) else [obj]

    def is_call(d):
        return isinstance(d, dict) and (("name" in d and ("arguments" in d or "parameters" in d))
                                        or "tool_call" in d or "tool_calls" in d
                                        or isinstance(d.get("function"), dict))
    return bool(items) and all(is_call(d) for d in items)


def _post(url, headers, body, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            last = f"network: {e}"
            time.sleep(2 ** i)
            continue
        if r.status_code in (429, 500, 502, 503, 504, 529):
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            ra = r.headers.get("retry-after")
            time.sleep(float(ra) if ra and ra.replace('.', '', 1).isdigit() else 2 ** (i + 1))
            continue
        if r.status_code != 200:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:500]}")
        return r.json()
    raise ProviderError(last or "request failed")


# =============================================================== providers
# Each provider exposes: new(system, prompt) -> state; step(state, tools, allow_tools) ->
# (text, calls[(id,name,args)], usage(in,out), extra_cost_or_None); add_results(state, calls, results).

class OpenAICompat:
    """OpenRouter + local llama.cpp (OpenAI chat-completions shape)."""

    def __init__(self, base, key, model, max_tokens=4096, extra=None, name="openrouter"):
        self.base, self.key, self.model = base.rstrip("/"), key, model
        self.max_tokens, self.extra, self.name = max_tokens, extra or {}, name

    def tools_fmt(self, mcp_tools):
        return [{"type": "function", "function": {
            "name": t["name"], "description": t.get("description", "")[:1024],
            "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}}
            for t in mcp_tools]

    def new(self, system, prompt):
        msgs = [{"role": "system", "content": system}] if system else []
        msgs.append({"role": "user", "content": prompt})
        return {"messages": msgs}

    def step(self, st, tools, allow_tools):
        body = {"model": self.model, "messages": st["messages"], "max_tokens": self.max_tokens}
        if self.name == "openrouter":
            body["usage"] = {"include": True}
        body.update(self.extra)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto" if allow_tools else "none"
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        d = _post(self.base + "/chat/completions", h, body)
        if "choices" not in d or not d["choices"]:
            raise ProviderError(f"no choices: {json.dumps(d)[:300]}")
        msg = d["choices"][0]["message"]
        st["messages"].append({k: v for k, v in msg.items() if v is not None})
        calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_unparseable": tc["function"].get("arguments")}
            calls.append((tc.get("id") or f"call_{len(calls)}", tc["function"]["name"], args))
        u = d.get("usage") or {}
        return (msg.get("content") or ""), calls, (u.get("prompt_tokens", 0), u.get("completion_tokens", 0)), u.get("cost")

    def add_results(self, st, calls, results):
        for (cid, name, _), res in zip(calls, results):
            st["messages"].append({"role": "tool", "tool_call_id": cid, "content": res})

    def add_user(self, st, text):
        st["messages"].append({"role": "user", "content": text})


class Anthropic:
    """Claude Messages API over raw HTTP (anthropic SDK is not installed; project is stdlib+requests).
    No server-side refusal fallbacks on purpose: a fallback would swap the model under test."""
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, key, model, max_tokens=16000, extra=None, workspace_id=None):
        self.key, self.model, self.max_tokens, self.extra = key, model, max_tokens, extra or {}
        self.workspace_id = workspace_id  # org-scoped keys are rejected without anthropic-workspace-id

    def tools_fmt(self, mcp_tools):
        return [{"name": t["name"], "description": t.get("description", ""),
                 "input_schema": t.get("inputSchema") or {"type": "object", "properties": {}}}
                for t in mcp_tools]

    def new(self, system, prompt):
        return {"system": system, "messages": [{"role": "user", "content": prompt}]}

    def step(self, st, tools, allow_tools):
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": st["messages"]}
        if st["system"]:
            body["system"] = st["system"]
        if tools:
            body["tools"] = tools
            body["tool_choice"] = {"type": "auto" if allow_tools else "none"}
        body.update(self.extra)
        h = {"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self.workspace_id:
            h["anthropic-workspace-id"] = self.workspace_id
        d = _post(self.URL, h, body)
        if d.get("stop_reason") == "refusal":
            raise ProviderError(f"refusal: {json.dumps(d.get('stop_details'))[:300]}")
        content = d.get("content", [])
        st["messages"].append({"role": "assistant", "content": content})  # echo verbatim (thinking blocks)
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        calls = [(b["id"], b["name"], b.get("input") or {}) for b in content if b.get("type") == "tool_use"]
        u = d.get("usage") or {}
        tin = (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
               + u.get("cache_read_input_tokens", 0))
        return text, calls, (tin, u.get("output_tokens", 0)), None

    def add_results(self, st, calls, results):
        st["messages"].append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": res} for (cid, _, _), res in zip(calls, results)]})

    def add_user(self, st, text):
        last = st["messages"][-1]
        if last["role"] == "user" and isinstance(last["content"], list):   # after unanswered tool results
            last["content"].append({"type": "text", "text": text})
        else:
            st["messages"].append({"role": "user", "content": text})


class Gemini:
    """generativelanguage.googleapis.com v1beta generateContent."""

    def __init__(self, key, model, max_tokens=8192, extra=None):
        self.key, self.model, self.max_tokens, self.extra = key, model, max_tokens, extra or {}

    def tools_fmt(self, mcp_tools):
        return [{"functionDeclarations": [{
            "name": t["name"], "description": t.get("description", ""),
            "parametersJsonSchema": t.get("inputSchema") or {"type": "object", "properties": {}}}
            for t in mcp_tools]}]

    def new(self, system, prompt):
        return {"system": system, "contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    def step(self, st, tools, allow_tools):
        body = {"contents": st["contents"], "generationConfig": {"maxOutputTokens": self.max_tokens}}
        if st["system"]:
            body["systemInstruction"] = {"parts": [{"text": st["system"]}]}
        if tools:
            body["tools"] = tools
            body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO" if allow_tools else "NONE"}}
        body.update(self.extra)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        d = _post(url, {"x-goog-api-key": self.key, "Content-Type": "application/json"}, body)
        cands = d.get("candidates") or []
        if not cands:
            raise ProviderError(f"no candidates: {json.dumps(d.get('promptFeedback'))[:300]}")
        content = cands[0].get("content") or {"role": "model", "parts": []}
        st["contents"].append(content)  # verbatim, keeps thoughtSignature parts
        parts = content.get("parts", [])
        text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
        calls = [(f"g{i}", p["functionCall"]["name"], p["functionCall"].get("args") or {})
                 for i, p in enumerate(parts) if "functionCall" in p]
        u = d.get("usageMetadata") or {}
        tout = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        return text, calls, (u.get("promptTokenCount", 0), tout), None

    def add_results(self, st, calls, results):
        st["contents"].append({"role": "user", "parts": [
            {"functionResponse": {"name": name, "response": {"content": res}}}
            for (_, name, _), res in zip(calls, results)]})

    def add_user(self, st, text):
        last = st["contents"][-1]
        if last.get("role") == "user":
            last["parts"].append({"text": text})
        else:
            st["contents"].append({"role": "user", "parts": [{"text": text}]})


class Mock:
    """Zero-network provider for --dry-run. Deterministic per qid:
    bare -> gold cite (real) + a fabricated cite; question ids whose number is a multiple of 5 abstain.
    mcp  -> pretends to call check_citation once, then answers with the gold cite only."""

    def __init__(self, arm):
        self.arm = arm

    def tools_fmt(self, mcp_tools):
        return mcp_tools

    def new(self, system, prompt):
        return {"q": None, "turn": 0}

    def step(self, st, tools, allow_tools):
        q = st["q"]
        digits = "".join(ch for ch in q["id"] if ch.isdigit())
        h = int(digits) if digits else int(hashlib.sha1(q["id"].encode()).hexdigest(), 16)
        st["turn"] += 1
        fake = ("Zelmanowitz v. Brightwater Holdings, LLC, 487 So. 3d 9921, 9925 (Fla. 4th DCA 2019)")
        if self.arm == "mcp" and allow_tools and st["turn"] == 1:
            return "", [("mock1", "check_citation", {"citation": q.get("gold_citation", "")})], (900, 40), None
        if self.arm == "bare" and h % 5 == 0:
            return ("I am not certain of a controlling citation for this proposition and cannot verify one "
                    "without research, so I will not guess."), [], (180, 40), None
        ans = f"The controlling authority is {q.get('gold_citation')}."
        if self.arm == "mcp" and q.get("gold_flag") in ("yellow", "red"):
            ans += " Caution: the research tools show this case has been overruled; do not rely on it."
        if self.arm == "bare":
            ans += f" See also {fake} (applying the same rule)."
        if st.get("revise"):
            ans += " (revised after self-check)"
        return ans, [], (180 if self.arm == "bare" else 2400, 90), None

    def add_results(self, st, calls, results):
        pass

    def add_user(self, st, text):
        st["revise"] = text


class ClaudeCode:
    """One question = one headless `claude -p` subprocess (Claude Code harness, SUBSCRIPTION auth: no API key in
    its environment). mcp arm: ONLY the Syfert MCP (--strict-mcp-config + .ccrun/mcp.json), every built-in tool
    removed (--tools ""), mcp__syfert__* pre-approved. bare arm: empty MCP config, no tools at all.
    Runs from the dedicated clean cwd .ccrun/ with --setting-sources "" so no user/project settings, hooks or
    CLAUDE.md load, and --no-session-persistence. Parses --output-format stream-json for per-tool calls."""
    CWD = os.path.join(ROOT, ".ccrun")
    SCRUB = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "OPENROUTER_API_KEY",
             "GEMINI_API_KEY", "SYFERT_MCP_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")
    BARE_SYSTEM = "You are a helpful legal research assistant. Answer the user's question directly as plain text."

    def __init__(self, model, arm, max_turns=10, timeout=900):
        self.model, self.arm, self.max_turns, self.timeout = model, arm, max_turns, timeout
        self.max_tokens = None
        mcp = os.path.join(self.CWD, "mcp.json" if arm == "mcp" else "mcp_empty.json")
        if not os.path.exists(mcp):
            raise SystemExit(f"claudecode: {mcp} missing (Syfert server config, chmod 600, lives in .ccrun/)")
        self.mcp = mcp
        self.system = MCP_SYSTEM if arm == "mcp" else self.BARE_SYSTEM

    def argv(self, prompt, max_turns=None):
        a = ["claude", "-p", prompt, "--model", self.model, "--strict-mcp-config", "--mcp-config", self.mcp,
             "--tools", "", "--setting-sources", "", "--no-session-persistence",
             "--system-prompt", self.system, "--max-turns", str(max_turns or self.max_turns),
             "--output-format", "stream-json", "--verbose"]
        if self.arm == "mcp":
            a += ["--allowedTools", "mcp__syfert__*"]
        return a

    def run(self, q, checker=None):
        """checker(text) -> (findings, _self_check record) turns on --self-check (see module docstring)."""
        row, meta = self._invoke(q["prompt"])
        if checker is None or row["error"] or not (row["raw_answer"] or "").strip():
            return row, meta
        findings, info = checker(row["raw_answer"])
        tools = json.loads(row["tool_calls_json"])
        info["turn"] = meta.get("num_turns")
        tools.append(info)
        row["latency_s"] = round(row["latency_s"] + info["latency_s"], 2)
        if findings:
            left = self.max_turns - (meta.get("num_turns") or 0)
            info.update(revision_mode="fresh claude -p: question + draft + findings (no persisted session to resume)",
                        revision_turns_budget=max(1, left), over_budget_turn=left < 1)
            r2, m2 = self._invoke(CC_REVISE_PROMPT.format(question=q["prompt"], draft=row["raw_answer"],
                                                          findings=findings_json(findings)), max(1, left))
            for t in json.loads(r2["tool_calls_json"]):
                t["turn"] = len(tools) + 1
                tools.append(t)
            info.update(revision_tokens_in=r2["tokens_in"], revision_tokens_out=r2["tokens_out"])
            if r2["error"] or not (r2["raw_answer"] or "").strip():
                info["revision_error"] = (r2["error"] or "empty revised answer") + " (draft kept)"
            else:
                row["raw_answer"] = r2["raw_answer"]
                info["revised"] = True
            row["tokens_in"] += r2["tokens_in"]
            row["tokens_out"] += r2["tokens_out"]
            row["latency_s"] = round(row["latency_s"] + r2["latency_s"], 2)
            meta = dict(meta, draft_nominal_cost_usd=meta.get("nominal_cost_usd"), revision=m2,
                        nominal_cost_usd=(meta.get("nominal_cost_usd") or 0) + (m2.get("nominal_cost_usd") or 0))
        row["tool_calls_json"] = json.dumps(tools)
        return row, meta

    def _invoke(self, prompt, max_turns=None):
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in self.SCRUB}
        t0 = time.time()
        try:
            p = subprocess.run(self.argv(prompt, max_turns), cwd=self.CWD, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return {"raw_answer": None, "tool_calls_json": "[]", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                    "latency_s": round(time.time() - t0, 2), "error": f"timeout {self.timeout}s"}, {}
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
        lat = round(time.time() - t0, 2)
        if not result:
            return {"raw_answer": None, "tool_calls_json": json.dumps(tools), "tokens_in": 0, "tokens_out": 0,
                    "cost_usd": 0.0, "latency_s": lat,
                    "error": f"claude exit {p.returncode}: {(p.stderr or '')[-300:]}"}, {}
        u = result.get("usage") or {}
        tin = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
        err = None
        if result.get("is_error") or result.get("subtype") != "success":
            err = f"{result.get('subtype')}: {str(result.get('result') or result.get('api_error_status'))[:200]}"
        elif not (result.get("result") or "").strip():
            err = "empty final answer"
        meta = {"num_turns": result.get("num_turns"), "nominal_cost_usd": result.get("total_cost_usd"),
                "permission_denials": result.get("permission_denials"), "session_id": result.get("session_id"),
                "duration_ms": result.get("duration_ms"), "terminal_reason": result.get("terminal_reason"),
                "tools_offered": (init or {}).get("tools"), "mcp_servers": (init or {}).get("mcp_servers"),
                "memory_paths": (init or {}).get("memory_paths"), "apiKeySource": (init or {}).get("apiKeySource"),
                "model_served": list((result.get("modelUsage") or {}).keys())}
        return {"raw_answer": result.get("result") if not err or result.get("result") else None,
                "tool_calls_json": json.dumps(tools), "tokens_in": tin, "tokens_out": u.get("output_tokens") or 0,
                "cost_usd": 0.0, "latency_s": lat, "error": err}, meta


# =============================================================== runner
def build_provider(spec, arm, keys, dry):
    p = spec["provider"]
    mt = spec.get("max_tokens")
    extra = spec.get("extra")
    if dry or p == "mock":
        return Mock(arm)
    if p == "claudecode":
        return ClaudeCode(spec["model"], arm, spec.get("max_turns", 10))
    if p == "openrouter":
        if not keys.get("OPENROUTER_API_KEY"):
            raise SystemExit("OPENROUTER_API_KEY missing in keys.env")
        return OpenAICompat("https://openrouter.ai/api/v1", keys["OPENROUTER_API_KEY"], spec["model"],
                            mt or 4096, extra, "openrouter")
    if p == "anthropic":
        if not keys.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY missing in keys.env")
        if not keys.get("ANTHROPIC_WORKSPACE_ID"):
            raise SystemExit("ANTHROPIC_WORKSPACE_ID missing in keys.env (the key is org-scoped)")
        return Anthropic(keys["ANTHROPIC_API_KEY"], spec["model"], mt or 16000, extra,
                         keys["ANTHROPIC_WORKSPACE_ID"])
    if p == "gemini":
        if not keys.get("GEMINI_API_KEY"):
            raise SystemExit("GEMINI_API_KEY missing in keys.env")
        return Gemini(keys["GEMINI_API_KEY"], spec["model"], mt or 8192, extra)
    if p == "local":
        base = keys.get("LOCAL_OPENAI_BASE") or "http://127.0.0.1:8080/v1"
        try:
            r = requests.get(base.rstrip("/") + "/models", timeout=5)
            r.raise_for_status()
            served = r.json()["data"][0]["id"]
        except Exception as e:
            raise SystemExit(f"local: no OpenAI-compatible endpoint answering at {base} ({e}). "
                             "citebench never starts GPU services; bring one up yourself or set LOCAL_OPENAI_BASE.")
        return OpenAICompat(base, None, spec.get("model") or served, mt or 2048, extra, "local")
    raise SystemExit(f"unknown provider {p}")


def run_question(q, arm, prov, spec, mcp_tools_raw, tools_fmt, keys, max_turns, dry, tls,
                 tool_result_chars=DEFAULT_TOOL_RESULT_CHARS, self_check=False):
    t0 = time.time()
    acc = {"tin": 0, "tout": 0, "cost": 0.0, "have_cost": False}
    tool_log = []
    system = MCP_SYSTEM if arm == "mcp" else BARE_SYSTEM
    st = prov.new(system, q["prompt"])
    if isinstance(prov, Mock):
        st["q"] = q

    def step(allow):
        text, calls, (i, o), c = prov.step(st, tools_fmt if arm == "mcp" else None, allow)
        acc["tin"] += i or 0
        acc["tout"] += o or 0
        if c is not None:
            acc["cost"] += float(c)
            acc["have_cost"] = True
        return text, calls

    def loop(first, last):
        """Model turns first..last (the last one tool-free); returns (final text, last turn used)."""
        text = ""
        for turn in range(first, last + 1):
            allow = arm == "mcp" and turn < last
            text, calls = step(allow)
            if (arm == "mcp" and not allow and isinstance(prov, OpenAICompat) and prov.name == "local"
                    and (calls or tool_call_leak(text))):
                # local llama.cpp: the forced tool-free turn still produced a tool call (as text, or parsed).
                # Drop that unusable assistant turn and give ONE more tool-free turn with a nudge; a second leak
                # is stored as error tool_call_leak (raw_answer NULL) so the resumable runner retries it.
                leak = {"turn": turn, "name": "_tool_call_leak", "leaked_text": (text or "")[:1000],
                        "leaked_calls": [[n, a] for _, n, a in calls], "nudge": TOOLS_CLOSED_NUDGE}
                st["messages"].pop()
                prov.add_user(st, TOOLS_CLOSED_NUDGE)
                text, calls = step(False)
                leak["nudged_ok"] = not calls and bool((text or "").strip()) and not tool_call_leak(text)
                tool_log.append(leak)
                if not leak["nudged_ok"]:
                    return (text if tool_call_leak(text) else ""), turn, True
                return text, turn, False
            if not calls or arm != "mcp":
                return text, turn, False
            results = []
            for cid, name, args in calls:
                t1 = time.time()
                if dry:
                    res, is_err = json.dumps({"mock": True, "tool": name}), False
                else:
                    if not hasattr(tls, "mcp"):
                        tls.mcp = MCPClient(keys.get("SYFERT_MCP_TOKEN"))
                    try:
                        res, is_err, _ = tls.mcp.call_tool(name, args)
                    except MCPError as e:
                        res, is_err = f"tool error: {e}", True
                full = len(res)
                if full > tool_result_chars:
                    res = res[:tool_result_chars] + f"\n...[truncated {full - tool_result_chars} chars]"
                tool_log.append({"turn": turn, "name": name, "args": args, "is_error": is_err,
                                 "result_chars": full, "fed_chars": len(res),
                                 "latency_s": round(time.time() - t1, 2)})
                results.append(res)
            prov.add_results(st, calls, results)
        return text, last, False

    text = ""
    try:
        text, used, leaked = loop(1, 1 if arm == "bare" else max_turns)
        err = None
        if leaked or tool_call_leak(text):
            err, text = TOOL_LEAK_ERROR, ""
        elif not (text or "").strip():
            err = "empty final answer"
        elif self_check and arm == "mcp":
            findings, info = run_self_check(text, q, keys, tls, dry)
            info["turn"] = used
            tool_log.append(info)
            if findings:
                first = used + 1
                last = max(max_turns, first)   # the revision always gets at least one (tool-free) turn
                info.update(revision_turns_budget=last - first + 1, over_budget_turn=first > max_turns)
                tin0, tout0 = acc["tin"], acc["tout"]
                prov.add_user(st, SELF_CHECK_PROMPT.format(findings=findings_json(findings)))
                try:
                    rev, _, rev_leaked = loop(first, last)
                    if rev_leaked or tool_call_leak(rev):
                        info["revision_error"] = "revision was a tool call, not an answer (draft kept)"
                    elif (rev or "").strip():
                        text = rev
                        info["revised"] = True
                    else:
                        info["revision_error"] = "empty revised answer (draft kept)"
                except Exception as e:     # the draft stands; the failure is on the record
                    info["revision_error"] = f"{type(e).__name__}: {e}"[:300] + " (draft kept)"
                info.update(revision_tokens_in=acc["tin"] - tin0, revision_tokens_out=acc["tout"] - tout0)
    except ProviderError as e:
        err = str(e)
    except Exception as e:  # keep the run going; recorded per question
        err = f"{type(e).__name__}: {e}"
    tin, tout = acc["tin"], acc["tout"]
    cost = acc["cost"] if acc["have_cost"] else (tin * spec["in_per_m"] + tout * spec["out_per_m"]) / 1e6
    return {"raw_answer": text if text else None, "tool_calls_json": json.dumps(tool_log),
            "tokens_in": tin, "tokens_out": tout, "cost_usd": round(cost, 6),
            "latency_s": round(time.time() - t0, 2), "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="key in models.json (default 'mock' with --dry-run)")
    ap.add_argument("--arm", required=True, choices=["bare", "mcp"])
    ap.add_argument("--questions", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="mock provider + mock tools, zero network")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--max-usd", type=float, default=None, help="stop scheduling new questions past this spend")
    ap.add_argument("--concurrency", type=int, default=None, help="default 4 (2 for local); capped at 4")
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--tag", default="v1", help="run_id suffix; change it to start a fresh run")
    ap.add_argument("--db", default=None, help="results db (default results/results.db)")
    ap.add_argument("--tool-result-chars", type=int, default=None,
                    help=f"truncate each tool result fed to the model (default: models.json tool_result_chars, "
                         f"else {DEFAULT_TOOL_RESULT_CHARS})")
    ap.add_argument("--self-check", action="store_true",
                    help="mcp only: check_brief the final answer and give the model one revision turn on findings "
                         "(run_id gets '+check')")
    a = ap.parse_args()
    if a.self_check and a.arm != "mcp":
        ap.error("--self-check applies to --arm mcp only")

    models = load_models()
    mkey = a.model or ("mock" if a.dry_run else None)
    if not mkey:
        ap.error("--model is required (or use --dry-run)")
    if mkey not in models["models"]:
        raise SystemExit(f"unknown model {mkey}; known: {', '.join(models['models'])}")
    spec = models["models"][mkey]
    if a.dry_run:
        mkey_run, spec = "mock", dict(models["models"]["mock"])
    else:
        mkey_run = mkey
    provider = "mock" if a.dry_run else spec["provider"]
    run_id = f"{mkey_run}:{a.arm}:{a.tag}" + ("+check" if a.self_check else "")
    trc = a.tool_result_chars or spec.get("tool_result_chars") or DEFAULT_TOOL_RESULT_CHARS

    qpath = a.questions or default_questions_path()
    qs = load_questions(qpath)
    if a.limit:
        qs = qs[:a.limit]

    con = open_db(a.db) if a.db else open_db()
    prev = con.execute("SELECT config_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if prev and prev[0]:
        pc = json.loads(prev[0])
        if pc.get("tool_result_chars", DEFAULT_TOOL_RESULT_CHARS) != trc:
            raise SystemExit(f"{run_id} was started with tool_result_chars={pc.get('tool_result_chars')}; this "
                             f"invocation would use {trc}. Pass --tool-result-chars {pc.get('tool_result_chars')} "
                             "to resume it, or --tag to start a fresh run.")
    done = {r[0] for r in con.execute(
        "SELECT qid FROM answers WHERE run_id=? AND error IS NULL", (run_id,))}
    todo = [q for q in qs if q["id"] not in done]

    # ---- cost gate (before any network)
    est = models["estimates"][a.arm]
    est_usd = len(todo) * (est["tokens_in"] * spec["in_per_m"] + est["tokens_out"] * spec["out_per_m"]) / 1e6
    if a.self_check:
        est_usd *= 2   # upper bound: a revision can re-run the whole tool loop once
    print(f"run_id={run_id} provider={provider} questions={len(qs)} (file {qpath}) "
          f"already_done={len(qs) - len(todo)} to_run={len(todo)}")
    print(f"cost estimate: {len(todo)} q x ({est['tokens_in']} in @ ${spec['in_per_m']}/M + "
          f"{est['tokens_out']} out @ ${spec['out_per_m']}/M)" + (" x2 (self-check upper bound)" if a.self_check else "")
          + f" = ${est_usd:.4f}")
    paid = provider in ("openrouter", "anthropic", "gemini")
    budget = (models.get("budgets_usd") or {}).get(provider)
    if paid and budget is not None:
        print(f"budget for {provider}: ${budget} -> this run is {100 * est_usd / budget:.1f}% of it"
              if budget else f"budget for {provider}: $0 (no credit recorded)")
        if est_usd > budget:
            print("WARNING: estimate exceeds the recorded budget for this provider.")
    if paid and todo and not a.confirm_spend:
        raise SystemExit("refusing a paid run without --confirm-spend (estimate above).")
    if not todo:
        print("nothing to do.")
        return

    keys = load_keys()
    prov = build_provider(spec, a.arm, keys, a.dry_run)
    mcp_tools_raw, tools_fmt = [], None
    if isinstance(prov, ClaudeCode):
        pass            # the harness connects to the MCP itself; tools are logged per question from its init event
    elif a.arm == "mcp":
        if a.dry_run:
            mcp_tools_raw = [{"name": "check_citation", "description": "mock", "inputSchema": {"type": "object"}}]
        else:
            c = MCPClient(keys.get("SYFERT_MCP_TOKEN"))
            mcp_tools_raw = c.list_tools()
            print(f"mcp: {c.server_info.get('name')} {c.server_info.get('version')} "
                  f"tools={len(mcp_tools_raw)}")
        tools_fmt = prov.tools_fmt(mcp_tools_raw)

    served_model = getattr(prov, "model", spec.get("model"))
    cfg = {"model_key": mkey_run, "model_id": served_model, "arm": a.arm, "questions": qpath,
           "max_turns": a.max_turns, "tool_result_chars": trc, "self_check": a.self_check,
           "self_check_prompt": SELF_CHECK_PROMPT if a.self_check else None,
           "system": MCP_SYSTEM if a.arm == "mcp" else BARE_SYSTEM,
           "max_tokens": getattr(prov, "max_tokens", None), "extra": spec.get("extra"),
           "tools": [t["name"] for t in mcp_tools_raw], "dry_run": a.dry_run,
           "price_in_per_m": spec["in_per_m"], "price_out_per_m": spec["out_per_m"]}
    if isinstance(prov, ClaudeCode):
        cfg.update(harness="claude-code", system=prov.system, max_turns=prov.max_turns,
                   argv_template=prov.argv("<prompt>"), cwd=prov.CWD, cc_meta={},
                   note="subscription (claude -p OAuth, no API key); nominal cost = sum of total_cost_usd in cc_meta")
        if a.self_check:
            cfg.update(self_check_prompt=CC_REVISE_PROMPT,
                       self_check_mode="fresh claude -p with question + draft + findings (no --resume: "
                                       "--no-session-persistence)")
    con.execute("INSERT OR IGNORE INTO runs (run_id, model, provider, arm, started_ts, config_json) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, served_model, provider, a.arm, dt.datetime.now().isoformat(timespec="seconds"),
                 json.dumps(cfg)))
    con.commit()

    conc = min(4, a.concurrency or (2 if provider in ("local", "claudecode") else 4))
    lock = threading.Lock()
    tls = threading.local()
    spent = [0.0]
    stop = threading.Event()

    def work(q):
        if stop.is_set():
            return q["id"], None
        meta = None
        if isinstance(prov, ClaudeCode):
            r, meta = prov.run(q, (lambda t: run_self_check(t, q, keys, tls, a.dry_run)) if a.self_check else None)
        else:
            r = run_question(q, a.arm, prov, spec, mcp_tools_raw, tools_fmt, keys, a.max_turns, a.dry_run, tls,
                             trc, a.self_check)
        if r["raw_answer"] and tool_call_leak(r["raw_answer"]):   # any provider: a tool call is not an answer
            tl = json.loads(r["tool_calls_json"] or "[]")
            tl.append({"name": "_tool_call_leak", "leaked_text": r["raw_answer"][:1000], "nudged_ok": False})
            r.update(raw_answer=None, error=TOOL_LEAK_ERROR, tool_calls_json=json.dumps(tl))
        with lock:
            if meta is not None:
                row = con.execute("SELECT config_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
                c0 = json.loads(row[0]) if row and row[0] else {}
                c0.setdefault("cc_meta", {})[q["id"]] = meta
                c0["nominal_cost_usd_total"] = round(sum((m.get("nominal_cost_usd") or 0)
                                                         for m in c0["cc_meta"].values()), 4)
                con.execute("UPDATE runs SET config_json=? WHERE run_id=?", (json.dumps(c0), run_id))
            con.execute("INSERT OR REPLACE INTO answers (run_id, qid, raw_answer, tool_calls_json, tokens_in, "
                        "tokens_out, cost_usd, latency_s, error) VALUES (?,?,?,?,?,?,?,?,?)",
                        (run_id, q["id"], r["raw_answer"], r["tool_calls_json"], r["tokens_in"],
                         r["tokens_out"], r["cost_usd"], r["latency_s"], r["error"]))
            con.commit()
            spent[0] += r["cost_usd"] or 0
            if a.max_usd is not None and spent[0] >= a.max_usd:
                stop.set()
        return q["id"], r

    n_err = 0
    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        for qid, r in ex.map(work, todo):
            if r is None:
                continue
            tl = json.loads(r["tool_calls_json"])
            chk = next((t for t in tl if t.get("name") == "_self_check"), None)
            ntc = len(tl) - (chk is not None)
            n_err += bool(r["error"])
            print(f"  {qid}: {r['latency_s']:6.1f}s in={r['tokens_in']} out={r['tokens_out']} "
                  f"tools={ntc} ${r['cost_usd']:.4f}"
                  + (f"  check: {len(chk['findings'])} finding(s)" + (" -> revised" if chk.get("revised") else "")
                     + (" ERROR " + chk["error"][:80] if chk.get("error") else "") if chk else "")
                  + (f"  ERROR {r['error'][:120]}" if r["error"] else ""))
            sys.stdout.flush()
    print(f"done run_id={run_id}: {len(todo)} attempted, {n_err} errors, spent ${spent[0]:.4f}"
          + ("  (stopped at --max-usd)" if stop.is_set() else ""))


if __name__ == "__main__":
    main()

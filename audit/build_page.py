#!/usr/bin/env python3
# usage: python3 audit/build_page.py [--packet PATH] [--out PATH]   (default: audit/packet.json -> audit/index.html)
"""Render the citebench grader-audit review page. The isyfert.com vhost parses .html as PHP,
so the embedded JSON escapes '<' (no '<?' can reach the page source)."""
import argparse, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
_ap = argparse.ArgumentParser()
_ap.add_argument("--packet", default=os.path.join(HERE, "packet.json"))
_ap.add_argument("--out", default=os.path.join(HERE, "index.html"))
ARGS = _ap.parse_args()
p = json.load(open(ARGS.packet))
data = json.dumps(p, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
html = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Citebench Grader Audit</title>
<style>
:root{--paper:#f6f5f1;--card:#fff;--ink:#1d1d1b;--soft:#55534e;--faint:#8a877f;--rule:#dedbd2;
--accent:#1f5fa8;--good:#1d7a46;--good-bg:#e6f4ec;--bad:#b3261e;--bad-bg:#fbe9e7;--mid:#8a6100;--mid-bg:#fbf2dc;
--hl:#fff1a8;--hl-ink:#1d1d1b;--quote-bg:#f1efe8;--ref-hl:#dbe8f8}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#141414;--card:#1e1e1d;--ink:#ecebe6;
--soft:#b9b6ad;--faint:#8c8980;--rule:#34332f;--accent:#7fb0ee;--good:#6fcf97;--good-bg:#173524;--bad:#f28b82;
--bad-bg:#3a1b19;--mid:#e8c16a;--mid-bg:#352b12;--hl:#5a4d0e;--hl-ink:#fff6cc;--quote-bg:#262624;--ref-hl:#1c3350}}
:root[data-theme="dark"]{--paper:#141414;--card:#1e1e1d;--ink:#ecebe6;--soft:#b9b6ad;--faint:#8c8980;--rule:#34332f;
--accent:#7fb0ee;--good:#6fcf97;--good-bg:#173524;--bad:#f28b82;--bad-bg:#3a1b19;--mid:#e8c16a;--mid-bg:#352b12;
--hl:#5a4d0e;--hl-ink:#fff6cc;--quote-bg:#262624;--ref-hl:#1c3350}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--rule);padding:10px 16px}
header .row{max-width:1100px;margin:0 auto;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0;flex:1 1 auto}
.bar{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;flex:1 1 160px;max-width:260px}
.bar i{display:block;height:100%;background:var(--good);width:0}
#count{font-variant-numeric:tabular-nums;color:var(--soft);font-size:14px}
button.theme{background:none;border:1px solid var(--rule);color:var(--soft);border-radius:6px;padding:3px 8px;cursor:pointer}
main{max-width:1100px;margin:0 auto;padding:16px}
.intro{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px 18px;margin-bottom:18px}
.intro p{margin:.4em 0}
h2.sec{font-size:17px;margin:28px 0 10px;color:var(--soft);text-transform:uppercase;letter-spacing:.04em}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px 18px;margin:0 0 16px}
.card.done{border-left:5px solid var(--good)}
.ask{font-weight:600;margin:0 0 8px}
.meta{font-size:13px;color:var(--faint);margin-bottom:8px;display:flex;gap:10px;flex-wrap:wrap}
.meta b{color:var(--soft);font-weight:600}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.cols{grid-template-columns:1fr}}
.pane h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint);margin:0 0 6px}
.quote{background:var(--quote-bg);border-radius:6px;padding:10px 12px;white-space:pre-wrap;word-wrap:break-word;font-family:Georgia,serif}
.ctx{font-size:13px;color:var(--soft);margin-top:6px;white-space:pre-wrap;word-wrap:break-word}
.ctx summary{cursor:pointer;color:var(--faint)}
mark{background:var(--hl);color:var(--hl-ink);padding:0 1px}
mark.ref{background:var(--ref-hl);color:var(--ink);border-bottom:2px solid var(--accent)}
.attr{margin:6px 0 10px;padding:8px 12px;border:1px solid var(--rule);border-radius:6px;font-size:14px}
.attr p{margin:3px 0}
.attr .lab{color:var(--faint);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.sentence{background:var(--quote-bg);border-radius:6px;padding:8px 12px;font-size:14px;white-space:pre-wrap;word-wrap:break-word;margin-top:4px}
.warn{color:var(--mid)}
.none{color:var(--faint);font-style:italic}
.call{margin:12px 0 8px;padding:8px 12px;border-radius:6px;font-size:14px}
.call.absent,.call.name_mismatch{background:var(--bad-bg)}
.call.found{background:var(--good-bg)}
.call .v{font-weight:700}
.judge{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:flex-start;margin-top:10px}
.opts label{display:block;margin:2px 0;cursor:pointer}
.opts small{color:var(--faint)}
textarea{width:100%;min-height:44px;background:var(--paper);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:6px 8px;font:inherit;font-size:14px}
.notes{flex:1 1 260px}
.save{background:var(--accent);color:var(--card);border:0;border-radius:6px;padding:7px 16px;font-weight:600;cursor:pointer}
.status{font-size:13px;color:var(--faint);margin-left:6px}
.status.ok{color:var(--good)}.status.err{color:var(--bad)}
.names{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:15px}
.names dt{color:var(--faint)}.names dd{margin:0}
.model{font-size:12px}
</style></head><body>
<header><div class="row"><h1>Citebench: check the "misgrounded" grader</h1>
<div class="bar"><i id="barfill"></i></div><span id="count">0 / 60 judged</span>
<button class="theme" id="themebtn" type="button">theme</button></div></header>
<main>
<div class="intro">
<p><b>The task.</b> An automatic grader decided whether each passage an AI model put in quotation marks really appears in the case(s) it cited. You check whether the grader got it right. Each card asks one question and gives you the quote next to the closest passage in the opinion.</p>
<p><b>Grader right</b> means the grader's call holds: an "absent" quote is not in any case the answer cites (allow punctuation, capitalization, brackets and ellipses, but not changed wording), or a "found" quote really is there. <b>Grader wrong</b> means the opposite, including when the "quote" is not offered as a quotation from a case at all (a rule text, a search phrase, a heading, scare quotes). Use <b>unsure</b> when the text shown isn't enough; the case link opens the full opinion.</p>
<p>The model's name is hidden to keep the check blind; click "show model" if you need it. Saves go to the server as you go; you can change an answer at any time.</p>
</div>
<h2 class="sec">Part 1: quoted passages (50)</h2><div id="quotes"></div>
<h2 class="sec">Part 2: case-name mismatches (10)</h2><div id="names"></div>
</main>
<script>
const P = __DATA__;
const saved = {};
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function hlCtx(ctx, q){ if(!ctx) return ""; const i = ctx.indexOf(q); if(i<0) return esc(ctx);
  return esc(ctx.slice(0,i)) + "<mark>" + esc(q) + "</mark>" + esc(ctx.slice(i+q.length)); }
function caseLink(c){ if(!c || !c.case_name) return '<span class="none">no resolved case</span>';
  const label = esc(c.bluebook || c.case_name);
  return c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${label}</a>` : label; }
function judgeBlock(it, defs){
  return `<div class="judge"><div class="opts">
  <label><input type="radio" name="v_${it.id}" value="right"> Grader right <small>${defs[0]}</small></label>
  <label><input type="radio" name="v_${it.id}" value="wrong"> Grader wrong <small>${defs[1]}</small></label>
  <label><input type="radio" name="v_${it.id}" value="unsure"> Unsure</label></div>
  <div class="notes"><textarea id="n_${it.id}" placeholder="Notes (optional)"></textarea>
  <button class="save" type="button" data-id="${it.id}">Save</button><span class="status" id="s_${it.id}"></span></div></div>`; }
function modelTag(it){ return `<details class="model"><summary>show model</summary>${esc(it.model)} (${esc(it.run_id)})</details>`; }
function marked(text, spans){ // spans: [[a,b,cls],...] non-overlapping offsets into text
  spans = spans.filter(x => x && x[0] != null && x[0] < x[1]).sort((x,y) => x[0]-y[0]);
  let out = "", at = 0;
  for (const [a,b,cls] of spans){ if(a < at) continue;
    out += esc(text.slice(at,a)) + `<mark${cls ? ' class="'+cls+'"' : ""}>` + esc(text.slice(a,b)) + "</mark>"; at = b; }
  return out + esc(text.slice(at)); }
function passageBlock(b, label){
  if(!b) return "";
  return b.run_words >= 3 ? `<div class="quote">…${esc(b.before)}<mark>${esc(b.match)}</mark>${esc(b.after)}…</div>
     <div class="ctx">Longest word-for-word run in ${label}: <b>${b.run_words} of ${b.quote_words}</b> words (${b.pct}%).${b.grader_searched ? "" : " <b>The grader did not search this opinion.</b>"}</div>`
     : `<div class="quote none">No run of 3 or more of the quote's words in ${label}.</div>`; }
function quoteCard(it){
  const absent = it.grader_verdict === "absent";
  const ask = absent ? "The grader says this quoted passage is NOT in any case the answer cites. Is that right?"
                     : "The grader says this quoted passage IS in a case the answer cites. Is that right?";
  const at = it.attribution || {}, cc = it.cited_case || {}, cb = it.check_brief;
  const searchedList = (at.searched || []).map(c => esc(c.case_name || ("cluster " + c.cluster_id))).join("; ") || "none";
  let graderLine;
  if (at.source === "grader") {
    graderLine = at.verdict === "found"
      ? `<p><span class="lab">Grader (${esc(at.grader_version)})</span><br>found in: <b>${caseLink(at.found_in)}</b>${at.kind ? " ("+esc(at.kind)+")" : ""}</p>
         <p class="ctx">Searched: ${searchedList}</p>`
      : `<p><span class="lab">Grader (${esc(at.grader_version)})</span><br>not found in any of: ${searchedList}${at.closest ? `; closest: <b>${caseLink(at.closest)}</b> (${esc(at.closest.ratio)})` : ""}${at.kind ? " · "+esc(at.kind) : ""}</p>`;
  } else {
    graderLine = `<p><span class="lab">Grader (${esc(at.grader_version || "unversioned")})</span><br>no per-quote record: the case below is the one the <b>answer</b> attributes the quote to, resolved from its text. Opinions the grader searched: ${searchedList}</p>`;
  }
  const notes = (it.attribution_notes || []).map(n => `<p class="ctx warn">${esc(n)}</p>`).join("");
  const modelLine = `<p><span class="lab">The answer attributes it to</span><br>${cc.case_name ? "<b>"+caseLink(cc)+"</b>" : (cc.unresolved ? "an unresolved cite: <b>"+esc(cc.raw)+"</b>" : '<span class="none">no citation found</span>')}
     ${cc.ref_text ? " · as written: “"+esc(cc.ref_text)+"”" : ""}${cc.via && cc.via !== "full citation" ? " · "+esc(cc.via) : ""} <span class="ctx">(${esc(cc.attributed_by)})</span></p>
     ${cc.note ? `<p class="ctx warn">${esc(cc.note)}</p>` : ""}
     ${cc.cluster_id && !cc.grader_searched ? `<p class="ctx warn">The grader did not search this case's text${cc.excluded_as_name_mismatch ? " (it flagged the case name as a mismatch)" : ""}.</p>` : ""}`;
  const m = it.answer_marks || {};
  const sentence = it.answer_sentence ? `<p><span class="lab">The answer's sentence (verbatim; quote highlighted, cite underlined)</span></p>
     <div class="sentence">${marked(it.answer_sentence, [m.quote && [m.quote[0], m.quote[1], ""], m.ref && [m.ref[0], m.ref[1], "ref"]])}</div>
     ${it.cite_sentence ? `<div class="sentence">${marked(it.cite_sentence.text, [[it.cite_sentence.ref[0], it.cite_sentence.ref[1], "ref"]])}</div>` : ""}` : "";
  const pc = it.passage_case;
  const plabel = pc ? "<b>"+esc(pc.case_name)+"</b>" : "";
  const best = pc ? (it.passage ? passageBlock(it.passage, plabel) : `<div class="quote none">No run of 3 or more of the quote's words in ${plabel}${it.cases_searched && !it.cases_searched.some(c => c.cluster_id === pc.cluster_id && c.text_chars) ? " (no opinion text)" : ""}.</div>`)
                  : `<div class="quote none">No case to show a passage from.</div>`;
  const el = it.longer_run_elsewhere;
  const elsewhere = el ? `<details class="ctx"><summary>A longer run is in ${esc(el.case_name)} (${el.run_words} of ${el.quote_words} words)</summary>${passageBlock(el, "<b>"+esc(el.case_name)+"</b>")}</details>` : "";
  const cbline = cb ? `check_brief's own check${cb.case_name ? " (paired with "+esc(cb.case_name)+")" : ""}: <b>${esc(cb.verdict)}</b>, source ${esc(cb.source)}, ${esc(cb.percent)}% similar${cb.best_match ? `; its closest passage: “${esc(cb.best_match)}”` : ""}` : "check_brief did not pair a quote check with this passage.";
  return `<div class="card" id="c_${it.id}"><div class="meta"><b>${it.id}</b><span>question ${esc(it.qid)}</span>${modelTag(it)}</div>
  <p class="ask">${ask}</p>
  <div class="attr">${graderLine}${notes}${modelLine}${sentence}</div>
  <div class="cols"><div class="pane"><h3>What the model wrote</h3><div class="quote">${esc(it.quote)}</div>
   ${it.context ? `<details class="ctx"><summary>surrounding answer text</summary>${hlCtx(it.context, it.quote)}</details>` : ""}</div>
  <div class="pane"><h3>Closest passage${pc ? " in "+esc(pc.case_name) : ""}</h3>${best}${elsewhere}</div></div>
  <div class="call ${it.grader_verdict}">Grader's call: <span class="v">${absent ? "QUOTE ABSENT (counts as misgrounded)" : "QUOTE FOUND (not counted)"}</span>
   <div class="ctx">${cbline}</div></div>
  ${judgeBlock(it, absent ? ["(it isn't in the opinion)","(it is there, or it isn't a case quote)"] : ["(it is there)","(it isn't there)"])}</div>`;
}
function nameCard(it){
  const rows = it.cites.map(c => `<dt>Cite as written</dt><dd>${esc(c.raw)}</dd>
    <dt>Name the model gave</dt><dd><b>${esc(c.claimed ? (c.claimed.lhs||"?") + " v. " + (c.claimed.rhs||"?") : "(none parsed)")}</b></dd>
    <dt>Case at that cite</dt><dd><b>${esc(c.resolved_name)}</b> · verdict ${esc(c.verdict)}</dd>`).join("");
  const rc = it.resolved_case;
  return `<div class="card" id="c_${it.id}"><div class="meta"><b>${it.id}</b><span>question ${esc(it.qid)}</span>${modelTag(it)}</div>
  <p class="ask">The grader says the case name the model wrote does NOT match the case at that citation. Is that right?</p>
  <dl class="names">${rows}<dt>Full cite</dt><dd>${caseLink(rc)} ${rc.court ? "· "+esc(rc.court) : ""} ${rc.date_filed ? "· "+esc(rc.date_filed) : ""}</dd></dl>
  ${it.context ? `<div class="ctx" style="margin-top:8px"><b>Answer text:</b> ${esc(it.context)}</div>` : ""}
  <div class="call name_mismatch">Grader's call: <span class="v">NAME MISMATCH (counts as misgrounded)</span></div>
  ${judgeBlock(it, ["(a different case sits at that cite)","(same case; abbreviation, party order or parsing noise)"])}</div>`;
}
function progress(){ const n = Object.keys(saved).length, t = P.items.length;
  document.getElementById("count").textContent = `${n} / ${t} judged`;
  document.getElementById("barfill").style.width = (100*n/t) + "%";
  P.items.forEach(it => document.getElementById("c_"+it.id).classList.toggle("done", !!saved[it.id])); }
function fill(id){ const s = saved[id]; if(!s) return;
  const r = document.querySelector(`input[name="v_${id}"][value="${s.verdict}"]`); if(r) r.checked = true;
  document.getElementById("n_"+id).value = s.note || "";
  document.getElementById("s_"+id).textContent = "saved " + (s.ts||"").replace("T"," ").slice(0,16); }
document.getElementById("quotes").innerHTML = P.items.filter(i=>i.section==="quote").map(quoteCard).join("");
document.getElementById("names").innerHTML = P.items.filter(i=>i.section==="name").map(nameCard).join("");
document.addEventListener("click", async e => {
  const btn = e.target.closest("button.save"); if(!btn) return;
  const id = btn.dataset.id, st = document.getElementById("s_"+id);
  const r = document.querySelector(`input[name="v_${id}"]:checked`);
  if(!r){ st.className="status err"; st.textContent="pick right / wrong / unsure first"; return; }
  const body = {id, verdict: r.value, note: document.getElementById("n_"+id).value};
  st.className="status"; st.textContent="saving…";
  try{ const res = await fetch("save.php",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const j = await res.json(); if(!j.ok) throw new Error(j.error||res.status);
    saved[id] = {verdict:body.verdict, note:body.note, ts:j.ts}; st.className="status ok"; st.textContent="saved"; progress();
  }catch(err){ st.className="status err"; st.textContent="save failed: " + err.message; }
});
fetch("save.php",{cache:"no-store"}).then(r=>r.json()).then(j=>{ Object.assign(saved,j); Object.keys(j).forEach(fill); progress(); }).catch(()=>progress());
(function(){ const root=document.documentElement, b=document.getElementById("themebtn");
  let t=null; try{ t=localStorage.getItem("cb-audit-theme"); }catch(e){}
  if(t) root.dataset.theme=t;
  b.addEventListener("click",()=>{ const dark = root.dataset.theme ? root.dataset.theme==="dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark"; try{ localStorage.setItem("cb-audit-theme", root.dataset.theme); }catch(e){} }); })();
</script></body></html>
"""
open(ARGS.out, "w").write(html.replace("__DATA__", data))
print("wrote", ARGS.out)

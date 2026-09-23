#!/usr/bin/env python3
# usage: python3 publish/build_methodology.py   (renders docs/METHODOLOGY.md -> publish/site/methodology.html)
import html, os, re, markdown
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "docs", "METHODOLOGY.md"), encoding="utf-8").read()
# placeholders like <proposition> are text, not HTML tags
src = re.sub(r"<(?!/?(?:a|br|em|strong|code|sup|sub|span|div|p)\b)([A-Za-z_][\w-]*)>", r"&lt;\1&gt;", src)
body = markdown.markdown(src, extensions=["tables", "fenced_code"])
# bare URLs -> links
body = re.sub(r'(?<![">])(https?://[^\s<)\]]+[^\s<)\].,;:])', r'<a href="\1">\1</a>', body)
# heading anchors: "## 4. Why ..." -> id="s4"
body = re.sub(r"<h2>(\d+)\. ", lambda m: f'<h2 id="s{m.group(1)}">{m.group(1)}. ', body)
assert "<?" not in body, "'<?' would be parsed as PHP on www.syfert.com (.html is PHP there)"
page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>citebench methodology</title>
<meta name="description" content="How citebench builds its questions, grades every citation, and where it can be wrong.">
<script>try{{var t=localStorage.getItem('sy-theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<style>
:root{{--paper:#fbfaf7;--ink:#1d1f23;--soft:#4a4f57;--rule:#dcd8cf;--accent:#1f5fa8;--code:#f1eee7;--warn-bg:#fff4d6;--warn-br:#d9b44a;--warn-ink:#5a4300;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15171a;--ink:#e7e5e0;--soft:#b3b0a8;--rule:#34373c;--accent:#8ab8f0;--code:#23262b;--warn-bg:#3a3014;--warn-br:#8a7020;--warn-ink:#f3dc9a;color-scheme:dark}}}}
:root[data-theme="dark"]{{--paper:#15171a;--ink:#e7e5e0;--soft:#b3b0a8;--rule:#34373c;--accent:#8ab8f0;--code:#23262b;--warn-bg:#3a3014;--warn-br:#8a7020;--warn-ink:#f3dc9a;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 Georgia,"Times New Roman",serif}}
main{{max-width:760px;margin:0 auto;padding:24px 16px 64px}}
a{{color:var(--accent);overflow-wrap:anywhere}}
h1,h2,h3{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.25}}
h1{{font-size:28px}} h2{{font-size:21px;margin-top:2em;border-top:1px solid var(--rule);padding-top:1em}}
table{{border-collapse:collapse;font:14px/1.4 system-ui,sans-serif;display:block;overflow-x:auto;max-width:100%}}
th,td{{border:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}}
code,pre{{font:14px ui-monospace,Menlo,Consolas,monospace;background:var(--code)}}
pre{{padding:10px;overflow-x:auto}} code{{padding:1px 3px}}
blockquote{{margin:1em 0;padding:0 1em;border-left:3px solid var(--rule);color:var(--soft)}}
.prelim-banner{{max-width:none;background:var(--warn-bg);border:1px solid var(--warn-br);color:var(--warn-ink);padding:10px 14px;font:15px/1.45 system-ui,sans-serif;margin:0 0 16px}}
.back{{font:15px system-ui,sans-serif}}
</style>
</head>
<body>
<main>
<p class="prelim-banner" role="note"><strong>Preliminary.</strong> Every figure on this page is preliminary until the grader audit is re-checked. Numbers may change.</p>
<p class="back"><a href="./">&larr; citebench results</a> &middot; source: <a href="data/METHODOLOGY.md">METHODOLOGY.md</a></p>
{body}
<p class="back"><a href="./">&larr; citebench results</a></p>
</main>
</body>
</html>
"""
open(os.path.join(ROOT, "publish", "site", "methodology.html"), "w", encoding="utf-8").write(page)
print("wrote publish/site/methodology.html", len(page), "bytes")

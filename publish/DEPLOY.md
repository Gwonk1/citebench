# citebench results page: deploy (STAGED, NOT DEPLOYED)

Nothing here has been copied to any host. Every line below is for Graham to run from xeric.

## Where it goes

syfert.com/mcp/ is served from the cloud host at `/storage/namedhosts/www.syfert.com/mcp/`
(graham-owned, not a git checkout, `.bak.*` convention; index.php and tools.php live there).
The results page is a new static directory under it:

    /storage/namedhosts/www.syfert.com/mcp/citebench/
      index.html          <- publish/site/index.html
      methodology.html    <- publish/site/methodology.html (rendered by publish/build_methodology.py)
      data/               <- questions.jsonl, report_150.md, report.md, METHODOLOGY.md
      charts/             <- publish/charts/*.svg + *.png (publish/site/charts is a symlink to ../charts)

URL: https://syfert.com/mcp/citebench/

Notes about that vhost:
- `.html` is run through PHP there (`AddType application/x-httpd-php .html` in the root .htaccess). The pages
  contain no `<?`; build_methodology.py asserts this. Keep it that way if you edit them.
- The root .htaccess denies .db/.sh/.py/.csv/.env etc. and backup-looking names; .jsonl, .md, .svg and .png are served.
- The site is behind Cloudflare. After any re-upload, check with `?cb=N` or purge /mcp/citebench/*.
- The caselaw PreToolUse hook blocks any scp/rsync command line that mentions a divergent file name such as
  index.php. The copy lines below only name the new citebench/ directory; the MCP page edit is done in place.

## Gates before going public

1. Re-look of audit cards Q06 Q08 Q12 Q16 Q27 Q29 Q37 Q45 done; if the absent/found precision changes, update the
   "Grader accuracy" bullet in index.html (and the "19 of 21" line in copy/reddit.md).
2. Confirm the g5 counts used on the page: absent 19/21, found 20/21, name 6/6. The 20/21 and 6/6 were derived
   from 95.2% and 100% (and the 4 name items g4 fixed); `audit/score.py < audit/verdicts_20260922.jsonl` still
   prints the g3 numbers.
3. DONE 2026-09-22 ~22:50 EDT (placeholders filled, sec. 4 on g5 counts, sec. 5 wording, sec. 7 real run, new sec. 8; html re-rendered, data/ copy refreshed). Was: docs/METHODOLOGY.md still contains `[Placeholder: ...]` notes (sections 2, 3, 6, 7); section 4 quotes the
   first-pass (g3) figures (0.3% / 2.6%, 18 of 20 unresolved were real) that differ from the g5 table (Fable
   0.4% / 1.9%, 11 of 755 unindexed); section 7 has a model/price table and a `citebench run` command that do not
   match the real run; section 5 says the standard terms "do not permit a harness like this one" (stronger than the
   page's "could not obtain access on terms allowing a published automated evaluation").
   methodology.html renders the markdown as-is. Fix docs/METHODOLOGY.md, then
   `python3 publish/build_methodology.py && cp docs/METHODOLOGY.md publish/site/data/`.
4. Charts present in publish/charts/ (headline_bars, fab_vs_misgrounded, bare_vs_mcp, index_gap; .svg and .png).
   Check that their numbers match the table.
5. Repository link: index.html has `[repository link to be added on release]` (span id="repo-url"). The local
   repo has no commits and no remote yet. copy/reddit.md and copy/x_thread.md have RESULTS_URL / REPO_URL.
6. Announcement date: index.html has `[date not set]` (span id="announce-date").

## Remove the preliminary banner (one line per page)

    cd ~/projects/citebench/publish/site
    sed -i '/class="prelim-banner"/d' index.html methodology.html
    # so a rebuild does not bring it back:
    sed -i '/class="prelim-banner"/d' ../build_methodology.py

The `.prelim-banner` CSS rule can stay; it styles nothing once the line is gone.

## Copy up

    cd ~/projects/citebench/publish
    ls charts/            # expect 8 files; the page shows broken images without them
    ssh cloud-ts 'mkdir -p /storage/namedhosts/www.syfert.com/mcp/citebench'
    rsync -avL --chmod=D775,F664 site/ cloud-ts:/storage/namedhosts/www.syfert.com/mcp/citebench/

`-L` copies the charts symlink as a real directory. Without rsync:

    ssh cloud-ts 'mkdir -p /storage/namedhosts/www.syfert.com/mcp/citebench/data /storage/namedhosts/www.syfert.com/mcp/citebench/charts'
    scp site/*.html cloud-ts:/storage/namedhosts/www.syfert.com/mcp/citebench/
    scp site/data/* cloud-ts:/storage/namedhosts/www.syfert.com/mcp/citebench/data/
    scp charts/*.svg charts/*.png cloud-ts:/storage/namedhosts/www.syfert.com/mcp/citebench/charts/

## Check

    curl -sI 'https://syfert.com/mcp/citebench/?cb=1' | head -5                       # 200, text/html
    curl -s  'https://syfert.com/mcp/citebench/?cb=1' | grep -c prelim-banner          # 1 while preliminary, 0 after
    curl -sI 'https://syfert.com/mcp/citebench/data/questions.jsonl' | grep -i content-type
    curl -sI 'https://syfert.com/mcp/citebench/charts/headline_bars.svg' | grep -i content-type   # image/svg+xml
    curl -s  'https://syfert.com/mcp/citebench/methodology.html?cb=1' | grep -c 'id="s4"'        # 1

Look at it once in light and once in dark mode (the page follows prefers-color-scheme and the site's
`sy-theme` localStorage value) and at phone width. It does not include topbar.php, so the topbar dark-mode
contract does not apply; every surface uses the page's own tokens.

## Link from the MCP page

copy/mcp_page_blurb.md is the text (124 words). It goes into `mcp/index.php` on the cloud host as a short
section just before `<h2 id="install">`. Edit in place on the cloud host after a backup:

    ssh cloud-ts 'cd /storage/namedhosts/www.syfert.com/mcp && cp -p index.php index.php.bak.pre-citebench-$(date +%Y%m%d-%H%M)'

HTML to paste (only h2, p and a, which that page already themes in both modes):

    <h2 id="citebench">How often do AI models cite real law?</h2>
    <p>citebench is our public test of citation integrity. Every model answers the same 150 legal research questions, and every citation is checked against 10.7 million U.S. opinions. The best frontier models now almost never invent a case (0.0% to 0.4% of citations), but 5.4% to 7.4% of their citations carry a wrong case name or a quotation that is not in the opinion. With these tools connected, Claude Sonnet 5 got that down to 1.9% (5 of 265 citations), and a 26B model running on one desktop GPU got it down to 2.8% (8 of 289). We built both the tools and the grader, and the results page says so. <a href="/mcp/citebench/">See the results and methodology</a>.</p>

Then `ssh cloud-ts 'php -l /storage/namedhosts/www.syfert.com/mcp/index.php'` and load https://syfert.com/mcp/?cb=1.

#!/usr/bin/env python3
"""
Build out/index.html, a landing page for the GitHub Pages deploy that links
to each standalone section build and to the merged-into-index.bs build. Run
after build.sh, from the repo root: `python3 tools/render_landing.py`.

Not a bare directory listing: this is the only entry point a visitor to the
Pages site sees, so it has to name what each link actually is.
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SECTIONS_DIR = HERE / "sections"
OUT_DIR = HERE / "out"

SECTION_ORDER = [
    "match-patterns",
    "globs",
    "permissions-api",
    "host-permissions",
    "version-number-handling",
    "extension-ids",
]


def read_metadata(name):
    text = (SECTIONS_DIR / f"{name}.bs").read_text(encoding="utf-8")
    title_m = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    abstract_m = re.search(r"^Abstract:\s*(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else name
    abstract = abstract_m.group(1).strip() if abstract_m else ""
    return title, abstract


def main():
    rows = []
    for name in SECTION_ORDER:
        html_path = OUT_DIR / "standalone" / f"{name}.html"
        if not html_path.exists():
            print(f"missing build output: {html_path}", file=sys.stderr)
            sys.exit(1)
        title, abstract = read_metadata(name)
        rows.append(
            f"<tr><td><a href=\"standalone/{html.escape(name)}.html\">"
            f"{html.escape(title)}</a></td>"
            f"<td>{html.escape(abstract)}</td></tr>"
        )

    merged_path = OUT_DIR / "merged" / "index.html"
    if not merged_path.exists():
        print(f"missing build output: {merged_path}", file=sys.stderr)
        sys.exit(1)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>quostibel</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; color: #111; }}
h1 {{ margin-bottom: 0.2em; }}
.status {{ background: #fff3cd; border: 1px solid #d4b106; padding: 0.75em 1em; margin: 1em 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
td, th {{ border: 1px solid #ccc; padding: 0.5em 0.75em; text-align: left; vertical-align: top; }}
th {{ background: #f4f4f4; }}
footer {{ margin-top: 2em; font-size: 0.9em; color: #555; }}
</style>
</head>
<body>
<h1>quostibel</h1>
<p>Drafts for sections of the WebExtensions specification
(<code>w3c/webextensions</code> <code>specification/index.bs</code>), each
validated against Chromium, WebKit and Gecko source.</p>
<div class="status">
Nothing here has been proposed to the WECG. Nothing has been filed anywhere.
These are drafts for review.
</div>
<h2>Sections</h2>
<table>
<tr><th>Section</th><th>Description</th></tr>
{"".join(rows)}
</table>
<h2>Merged build</h2>
<p>All six sections spliced into a fresh copy of the real
<code>index.bs</code> and compiled as one document:
<a href="merged/index.html">merged/index.html</a>.</p>
<footer>
Source and build notes: see the repository README.
</footer>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {OUT_DIR / 'index.html'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# Compile every section under sections/*.bs standalone, then splice all six
# into a fresh copy of the real w3c/webextensions specification/index.bs and
# compile that too.
#
#   STANDALONE - each sections/<name>.bs already carries its own real
#     <pre class='metadata'> and <pre class="link-defaults"> blocks (see the
#     README for why), so it is handed to bikeshed directly, with no wrapper.
#     A pass here means zero fatal messages.
#
#   MERGED - the real specification/index.bs is fetched fresh from
#     w3c/webextensions on every run (`gh api`), the standalone preamble and
#     link-defaults block are stripped back out of each section (everything
#     after the "Standalone preamble" comment, minus the link-defaults pre
#     block that follows it), and the six resulting bodies are spliced into
#     their intended headings with tools/splice_merged.py. A pass here also
#     means zero fatal messages.
#
# Both modes use --die-on=nothing so bikeshed always finishes and reports
# everything, and tools/classify.py decides pass/fail from the --print=json
# message stream (bikeshed's own --die-on=fatal would refuse to generate any
# output the instant it saw a fatal, which makes it useless for reporting
# per-file results in one run). classify.py takes an optional list of
# "Couldn't find target document section <id>" ids to allow through as
# non-fatal; none are needed any more (see README), but the mechanism is
# still there and still used to fail on anything unexpected.
#
# Re-run any time: this script does not write into sections/*.bs, and it
# re-fetches index.bs from GitHub fresh each run rather than relying on a
# cached copy.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECTIONS="$HERE/sections"
TOOLS="$HERE/tools"
OUT="$HERE/out"

if [ -x "$HERE/bsvenv/bin/bikeshed" ]; then
  BIKESHED="$HERE/bsvenv/bin/bikeshed"
elif command -v bikeshed >/dev/null 2>&1; then
  BIKESHED="$(command -v bikeshed)"
else
  echo "bikeshed not found. Set up a venv first (see README.md: How to build)." >&2
  exit 1
fi

echo "== REGRESSION CHECKS =="
echo "-- Issue: shorthand leaking into normative text --"
python3 "$TOOLS/check_issue_leaks.py" "$SECTIONS"
echo
echo "-- autolink suffix outside the link (e.g. [=term=]ing) --"
python3 "$TOOLS/check_autolink_suffix.py" "$SECTIONS"
echo

rm -rf "$OUT"
mkdir -p "$OUT/standalone" "$OUT/merged"

MARKER="<!-- Standalone preamble. Remove metadata and link-defaults when splicing into index.bs. -->"

declare -A ROWDIR=(
  [match-patterns]="1-match-patterns"
  [globs]="2-globs"
  [permissions-api]="3-permissions-api"
  [host-permissions]="4-host-permissions"
  [version-number-handling]="5-version-handling"
  [extension-ids]="6-extension-ids"
)
SECTION_ORDER="match-patterns globs permissions-api host-permissions version-number-handling extension-ids"

echo "== STANDALONE =="
standalone_failures=0
for name in $SECTION_ORDER; do
  echo "-- $name --"
  "$BIKESHED" --die-on=nothing --print=json spec \
    "$SECTIONS/$name.bs" "$OUT/standalone/$name.html" \
    > "$OUT/standalone/$name.messages.json" 2> "$OUT/standalone/$name.stderr.txt" || true
  if ! python3 "$TOOLS/classify.py" "$OUT/standalone/$name.messages.json"; then
    standalone_failures=$((standalone_failures + 1))
  fi
done

echo
echo "== MERGED =="

MERGE_SRC="$(mktemp -d)"
trap 'rm -rf "$MERGE_SRC"' EXIT

for name in $SECTION_ORDER; do
  row="${ROWDIR[$name]}"
  mkdir -p "$MERGE_SRC/$row"
  python3 - "$SECTIONS/$name.bs" "$MERGE_SRC/$row/draft.bs" "$MARKER" <<'PYEOF'
import sys
src, dst, marker = sys.argv[1:4]
with open(src, encoding="utf-8") as f:
    content = f.read()
after = content.split(marker, 1)[1]
ld_start = after.index('<pre class="link-defaults">')
ld_end = after.index('</pre>', ld_start) + len('</pre>')
stripped = (after[:ld_start] + after[ld_end:]).lstrip("\n")
with open(dst, "w", encoding="utf-8") as f:
    f.write(stripped)
PYEOF
done

FRESH_INDEX="$OUT/merged/index.bs.upstream"
gh api repos/w3c/webextensions/contents/specification/index.bs --jq .content \
  | base64 -d > "$FRESH_INDEX"

python3 "$TOOLS/splice_merged.py" "$FRESH_INDEX" "$MERGE_SRC" "$OUT/merged/index.bs"

"$BIKESHED" --die-on=nothing --print=json spec \
  "$OUT/merged/index.bs" "$OUT/merged/index.html" \
  > "$OUT/merged/messages.json" 2> "$OUT/merged/stderr.txt" || true

merged_pass=true
if ! python3 "$TOOLS/classify.py" "$OUT/merged/messages.json"; then
  merged_pass=false
fi

echo
echo "== REGRESSION CHECKS (post-build) =="
echo "-- double-escaped angle brackets (amp;lt;) in generated HTML --"
escaping_failures=0
if grep -rn "amp;lt;" "$OUT" --include='*.html'; then
  escaping_failures=1
fi
if [ "$escaping_failures" -eq 0 ]; then
  echo "  clean."
fi

echo
echo "== SUMMARY =="
echo "standalone failures: $standalone_failures / 6"
echo "merged: $([ "$merged_pass" = true ] && echo PASS || echo FAIL)"
echo "double-escaping regressions: $([ "$escaping_failures" -eq 0 ] && echo none || echo FOUND)"

if [ "$standalone_failures" -ne 0 ] || [ "$merged_pass" != true ] || [ "$escaping_failures" -ne 0 ]; then
  exit 1
fi

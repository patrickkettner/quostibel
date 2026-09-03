#!/usr/bin/env python3
"""
Guard against a gap in bikeshed's own "Complain About: accidental-2119"
check: bikeshed only treats `class="note"`, `"example"`, `"non-normative"`
and `"informative"` as non-normative for that check. `class="issue"` is NOT
in that list, so an RFC 2119 keyword written inside a `<div class=issue>`
block, or an `Issue:` shorthand paragraph, is never flagged even though an
issue is exactly the kind of non-normative text accidental-2119 exists to
police: an open question should not read as if it were already a
requirement.

This script closes that gap directly: it fails (prints file:line and exits
1) if `must`, `must not`, `shall`, `should`, `should not`, `required`, or
`recommended` appears inside a `<div class=issue>...</div>` block or an
`Issue:` shorthand paragraph. `may` and `optional` are excluded -- both are
too common in ordinary descriptive English to flag usefully.

A keyword that opens a question -- "Must an extension ID survive ...?", a
bulleted "* Must an implementation reject ...?", or a wrapped "Should ...
[newline] ... resolve?" -- is the house style for framing an open question
in these issues and is excluded. Only the leading word of such a question
is exempt; any other keyword elsewhere in the same issue is still flagged.
"""
import re
import sys
from pathlib import Path

KEYWORDS = [
    "must not",
    "must",
    "shall",
    "should not",
    "should",
    "required",
    "recommended",
]
KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b",
    re.IGNORECASE,
)
LEADING_KEYWORD_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b",
    re.IGNORECASE,
)
BULLET_RE = re.compile(r"^[*\-]\s+")


def find_question_opener_exemptions(block_lines: list[str]) -> set[tuple[int, int]]:
    """Return the set of (line offset within block, column) positions that
    are the leading word of a question-opener unit and should not be
    flagged."""
    exempt: set[tuple[int, int]] = set()
    n = len(block_lines)
    i = 0
    prev_blank = True
    while i < n:
        line = block_lines[i]
        stripped = line.strip()
        if stripped == "":
            prev_blank = True
            i += 1
            continue
        starts_bullet = bool(BULLET_RE.match(stripped))
        is_unit_start = prev_blank or starts_bullet
        if is_unit_start:
            unit_idx = [i]
            j = i + 1
            while j < n:
                nxt = block_lines[j].strip()
                if nxt == "" or BULLET_RE.match(nxt):
                    break
                unit_idx.append(j)
                j += 1
            joined = " ".join(block_lines[k].strip() for k in unit_idx)
            joined_no_marker = BULLET_RE.sub("", joined, count=1)
            if LEADING_KEYWORD_RE.match(joined_no_marker) and joined.rstrip().endswith("?"):
                marker_match = BULLET_RE.match(stripped)
                marker_len = len(marker_match.group(0)) if marker_match else 0
                leading_ws = len(line) - len(line.lstrip())
                exempt.add((i, leading_ws + marker_len))
        prev_blank = False
        i += 1
    return exempt


def scan_block(path: Path, block_lines: list[str], start_lineno: int) -> list[str]:
    """block_lines: the issue's own text, one entry per source line, in
    order. start_lineno: the source line number of block_lines[0]."""
    failures = []
    exempt = find_question_opener_exemptions(block_lines)
    for offset, line in enumerate(block_lines):
        for m in KEYWORD_RE.finditer(line):
            if (offset, m.start()) in exempt:
                continue
            lineno = start_lineno + offset
            failures.append(
                f"{path}:{lineno}: RFC 2119 keyword '{m.group(1)}' inside an issue "
                f"block (accidental-2119 does not see class=\"issue\"). "
                f"Line: {line.strip()!r}"
            )
    return failures


def check_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    failures = []
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if re.match(r"^<div\s+class=[\"']?issue[\"']?\s*>", stripped):
            # Collect until the matching </div>. These files do not nest
            # other divs inside an issue block.
            block = []
            block_start = i + 2  # line after the opening <div>, 1-indexed
            j = i + 1
            while j < n and "</div>" not in lines[j]:
                block.append(lines[j])
                j += 1
            failures.extend(scan_block(path, block, block_start))
            i = j + 1
            continue
        if stripped.startswith("Issue:"):
            # Shorthand paragraph: runs until the first blank line (see
            # check_issue_leaks.py for why that's where bikeshed itself
            # considers the paragraph closed).
            block = [lines[i][lines[i].index("Issue:") + len("Issue:") :]]
            block_start = i + 1  # 1-indexed line of the "Issue:" line itself
            j = i + 1
            while j < n and lines[j].strip() != "":
                block.append(lines[j])
                j += 1
            failures.extend(scan_block(path, block, block_start))
            i = j + 1
            continue
        i += 1
    return failures


def main() -> int:
    sections_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sections")
    all_failures = []
    for bs_file in sorted(sections_dir.glob("*.bs")):
        all_failures.extend(check_file(bs_file))
    if all_failures:
        print("RFC 2119 keyword in issue-block check FAILED:", file=sys.stderr)
        for f in all_failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print("RFC 2119 keyword in issue-block check: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

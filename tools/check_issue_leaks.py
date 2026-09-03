#!/usr/bin/env python3
"""
Guard against a specific silent-failure class in these drafts: bikeshed's
`Issue:` paragraph shorthand ends at the first blank line. If someone writes

    Issue: Some lead-in sentence.

    * A bullet meant to be part of the same issue.

the blank line already closed the issue at "sentence.", so the bullet list
renders as ordinary normative text instead of living inside the issue box.
This has happened before in this repo (see BUILD-NOTES.md) and produces no
bikeshed warning or error, so it has to be caught by inspection instead.

Fails (prints file:line and exits 1) if a paragraph starting with the
`Issue:` shorthand is followed by exactly one blank line and then a line
whose first non-space character is `*` or `-` (a bullet list).
Use a `<div class=issue>...</div>` block instead when the issue's content
needs more than one paragraph.
"""
import sys
from pathlib import Path

def check_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    failures = []
    in_issue_para = False
    saw_blank_after_issue = False
    for i, line in enumerate(lines):
        lineno = i + 1
        stripped = line.strip()
        if stripped.startswith("Issue:"):
            in_issue_para = True
            saw_blank_after_issue = False
            issue_start = lineno
            continue
        if in_issue_para:
            if stripped == "":
                if not saw_blank_after_issue:
                    saw_blank_after_issue = True
                    continue
                else:
                    # second consecutive blank line: issue paragraph is
                    # long since over, stop tracking it.
                    in_issue_para = False
                continue
            if saw_blank_after_issue:
                # first line after the blank that closed the Issue paragraph
                first_char = stripped[0] if stripped else ""
                if first_char in ("*", "-"):
                    failures.append(
                        f"{path}:{issue_start}: 'Issue:' shorthand is closed by a "
                        f"blank line and then a bullet at line {lineno}, which "
                        f"orphans the bullet into normative text. Use "
                        f"<div class=issue>...</div> instead."
                    )
                in_issue_para = False
                saw_blank_after_issue = False
            # else: still inside the same Issue paragraph (no blank line yet)
    return failures

def main() -> int:
    sections_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sections")
    all_failures = []
    for bs_file in sorted(sections_dir.glob("*.bs")):
        all_failures.extend(check_file(bs_file))
    if all_failures:
        print("Issue-shorthand leak check FAILED:", file=sys.stderr)
        for f in all_failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print("Issue-shorthand leak check: clean.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

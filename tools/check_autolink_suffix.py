#!/usr/bin/env python3
"""
Guard against a specific bikeshed autolink bug: `[=term=]` immediately
followed by a letter, with no separating space or piped display text, such
as `[=strictly split=]ting`. Bikeshed does not fold the trailing letters into
the link text; it prints the raw suffix immediately after the rendered link,
which reads as a typo on the published page. The fix is always the piped
display-text form: `[=strictly split|strictly splitting=]`.

Fails (prints file:line and exits 1) for every `=]` in a sections/*.bs file
that is directly followed by an ASCII letter.
"""
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"=\](?=[A-Za-z])")

def check_file(path: Path) -> list[str]:
    failures = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for m in PATTERN.finditer(line):
            col = m.start() + 1
            failures.append(
                f"{path}:{i}:{col}: '=]' is immediately followed by a letter "
                f"outside the autolink - use the piped display-text form "
                f"instead, e.g. [=term|display text=]."
            )
    return failures

def main() -> int:
    sections_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sections")
    all_failures = []
    for bs_file in sorted(sections_dir.glob("*.bs")):
        all_failures.extend(check_file(bs_file))
    if all_failures:
        print("Autolink-suffix check FAILED:", file=sys.stderr)
        for f in all_failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print("Autolink-suffix check: clean.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

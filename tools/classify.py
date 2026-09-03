#!/usr/bin/env python3
"""
Read a bikeshed --print=json output file and decide pass/fail.

A row PASSES if every 'fatal' message is a "Couldn't find target document
section <id>" error whose <id> is in the allowed set passed on argv (these
are the deliberate, documented cross-draft/cross-document references that
can only resolve once everything is spliced together - see build-drafts.sh
and rows/BUILD-NOTES.md for the exact list and why each one is expected).
Any other fatal, or a "Couldn't find..." fatal for an id NOT in the allowed
set, fails the row.

'link', 'warning' and 'lint' messages never fail a row on their own (this
matches bikeshed's own default --die-on=fatal behavior, and matches how the
pristine real index.bs already ships with ~25 such unresolved items) - they
are always printed for the record.
"""
import json
import re
import sys

def main():
    json_path = sys.argv[1]
    allowed_ids = set(sys.argv[2:])

    with open(json_path, encoding='utf-8') as f:
        messages = json.load(f)

    unexpected_fatals = []
    expected_fatals = []
    other = {'link': [], 'warning': [], 'lint': []}

    target_re = re.compile(r"Couldn't find target document section ([\w-]+):")

    for m in messages:
        t = m['messageType']
        if t == 'fatal':
            match = target_re.search(m['text'])
            target = match.group(1) if match else None
            if target is not None and target in allowed_ids:
                expected_fatals.append((target, m.get('lineNum')))
            else:
                unexpected_fatals.append(m)
        elif t in other:
            other[t].append(m)
        # 'success' ignored here, the exit code already tells us that

    passed = not unexpected_fatals

    print(f"    expected/suppressed fatals: {len(expected_fatals)} "
          f"({', '.join(sorted(set(t for t, _ in expected_fatals))) or 'none'})")
    print(f"    link: {len(other['link'])}  warning: {len(other['warning'])}  "
          f"lint: {len(other['lint'])}")
    if unexpected_fatals:
        print(f"    UNEXPECTED FATAL ERRORS: {len(unexpected_fatals)}")
        for m in unexpected_fatals:
            text = m['text'].replace('\n', ' / ')[:200]
            print(f"      [{m.get('lineNum')}] {text}")

    print("    RESULT:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()

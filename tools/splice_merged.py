#!/usr/bin/env python3
"""
Splice the six webextensions draft.bs rows into a fresh copy of the real
specification/index.bs, producing one document for the MERGED bikeshed
compile test.

This is deliberately NOT a generic "markdown section replace" tool: each of
the six splice points has its own shape (see WHERE EACH DRAFT SPLICES IN in
the task brief), and two of them needed a placement judgment call beyond
what the brief says literally. Both are called out below and in
rows/BUILD-NOTES.md:

  * row 4 (host-permissions) contains a `## User gestures and activeTab`
    section, tagged with an HTML comment in the draft itself saying it
    belongs under "# Concepts" (replacing the empty heading there), not
    under "# Host permissions". The task's splice map only mentions
    "# Host permissions ... including Cross-origin fetch" for row 4, so this
    script honours the draft's own explicit note for that one subsection and
    keeps the map's instruction for the rest of row 4.
  * row 5 (version-handling) opens with two `## Key` sections (`version`,
    `version_name`) followed by its own `# Version number handling` heading.
    Bikeshed treats headings out of document order as a heading-level jump
    (h1 -> h3 straight under "# Version number handling" is fatal), so this
    script reorders row 5's own content to [h1 heading, the two Key
    sections, everything else] when splicing, matching the evident intent
    (key definitions before the algorithm sections) without touching any
    prose. See rows/5-version-handling/draft.bs for the id changes that
    make this safe (new ids, 3 redirected self-references).
"""
import re
import sys

def heading_level(line):
    m = re.match(r'^(#+)\s', line)
    return len(m.group(1)) if m else None

def find_heading(lines, text_regex, start=0):
    """Find the first heading line whose visible text matches text_regex.
    Returns (index, level) or (None, None)."""
    pat = re.compile(text_regex)
    for i in range(start, len(lines)):
        lvl = heading_level(lines[i])
        if lvl is None:
            continue
        # Strip leading #'s, trailing #'s + {#id}, to get the visible text
        body = lines[i]
        body = re.sub(r'^#+\s*', '', body)
        body = re.sub(r'\s*#+\s*(\{#[^}]+\})?\s*$', '', body)
        if pat.search(body):
            return i, lvl
    return None, None

def section_end(lines, start, level):
    """Given the index of a heading line at `level`, find the index of the
    next line that starts a heading at level <= `level` (or len(lines))."""
    for i in range(start + 1, len(lines)):
        lvl = heading_level(lines[i])
        if lvl is not None and lvl <= level:
            return i
    return len(lines)

def replace_section(doc_lines, text_regex, new_content_lines):
    """Replace [heading_line, section_end) for the heading matching
    text_regex with new_content_lines (which normally repeats/updates the
    heading line itself plus the new body)."""
    idx, lvl = find_heading(doc_lines, text_regex)
    if idx is None:
        raise SystemExit(f"splice target not found: {text_regex!r}")
    end = section_end(doc_lines, idx, lvl)
    return doc_lines[:idx] + new_content_lines + doc_lines[end:]

def insert_after_section(doc_lines, text_regex, new_content_lines):
    """Insert new_content_lines as a new top-level block right after the
    section (heading + body) matching text_regex ends."""
    idx, lvl = find_heading(doc_lines, text_regex)
    if idx is None:
        raise SystemExit(f"splice anchor not found: {text_regex!r}")
    end = section_end(doc_lines, idx, lvl)
    return doc_lines[:end] + new_content_lines + doc_lines[end:]

def extract_section(lines, text_regex):
    """Return (before, section_lines, after) for the section matching
    text_regex, where section_lines includes the heading line."""
    idx, lvl = find_heading(lines, text_regex)
    if idx is None:
        raise SystemExit(f"section to extract not found: {text_regex!r}")
    end = section_end(lines, idx, lvl)
    return lines[:idx], lines[idx:end], lines[end:]

def read_lines(path):
    with open(path, encoding='utf-8') as f:
        return f.read().splitlines(keepends=False)

def as_lines(text):
    return text.splitlines(keepends=False)

def main():
    if len(sys.argv) != 4:
        print("usage: splice_merged.py <fresh-index.bs> <rows-dir> <out.bs>", file=sys.stderr)
        sys.exit(1)
    fresh_path, rows_dir, out_path = sys.argv[1:4]

    doc = read_lines(fresh_path)

    row1 = read_lines(f"{rows_dir}/1-match-patterns/draft.bs")
    row2 = read_lines(f"{rows_dir}/2-globs/draft.bs")
    row3 = read_lines(f"{rows_dir}/3-permissions-api/draft.bs")
    row4 = read_lines(f"{rows_dir}/4-host-permissions/draft.bs")
    row5 = read_lines(f"{rows_dir}/5-version-handling/draft.bs")
    row6 = read_lines(f"{rows_dir}/6-extension-ids/draft.bs")

    # --- split row4 into its "Host permissions" portion and its
    # "activeTab" portion, per the draft's own HTML-comment note. ---
    before4, activetab_section, after4 = extract_section(
        row4, r'^User gestures and activeTab$'
    )
    # Drop the HTML comment that announces the split (it is editorial
    # scaffolding for humans reviewing the draft file standalone, not
    # spec content) and any trailing blank lines left behind.
    host_perms_portion = []
    skip_comment = False
    for line in before4:
        if line.strip().startswith('<!--'):
            skip_comment = True
        if skip_comment:
            if '-->' in line:
                skip_comment = False
            continue
        host_perms_portion.append(line)
    while host_perms_portion and host_perms_portion[-1].strip() == '':
        host_perms_portion.pop()
    assert not after4 or all(l.strip() == '' for l in after4), \
        "unexpected content after activeTab section in row4"

    # --- reorder row5: [h1 Version number handling heading] + [the two
    # Key sections] + [everything else the h1 section already had]. ---
    idx5, lvl5 = find_heading(row5, r'^Version number handling$')
    assert lvl5 == 1
    h1_line = row5[idx5]
    key_sections = row5[:idx5]
    rest = row5[idx5 + 1:]
    while key_sections and key_sections[-1].strip() == '':
        key_sections.pop()
    row5_reordered = [h1_line, ''] + key_sections + [''] + rest

    # 1. Host permissions (+ Cross-origin fetch) <- row4 minus activeTab
    doc = replace_section(doc, r'^Host permissions$', host_perms_portion)

    # 2. New "permissions" API section, right after Host permissions
    doc = insert_after_section(doc, r'^Host permissions$', [''] + row3 + [''])

    # 3. Match patterns <- row1
    doc = replace_section(doc, r'^Match patterns$', row1)

    # 4. Globs <- row2
    doc = replace_section(doc, r'^Globs$', row2)

    # 5. Concepts > Uniqueness of extension IDs <- row6
    doc = replace_section(doc, r'^Uniqueness of extension IDs$', row6)

    # 6. Concepts > User gestures and activeTab <- row4's activeTab piece
    doc = replace_section(
        doc, r'^User gestures and activeTab$', activetab_section
    )

    # 7. Version number handling <- row5 (reordered)
    doc = replace_section(doc, r'^Version number handling$', row5_reordered)

    # 8. link-defaults: extend the block index.bs already keeps at the
    # bottom of the file, rather than adding a second one.
    new_defaults = [
        'spec:url; type:dfn; text:scheme',
        'spec:url; type:dfn; for:url; text:host',
        'spec:url; type:dfn; text:path',
        'spec:infra; type:dfn; text:user agent',
    ]
    for i, line in enumerate(doc):
        if line.strip() == '<pre class="link-defaults">':
            doc = doc[:i + 1] + new_defaults + doc[i + 1:]
            break
    else:
        raise SystemExit("could not find the existing link-defaults block")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(doc) + '\n')

if __name__ == '__main__':
    main()

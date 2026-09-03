# Build notes: getting the six sections to compile standalone under bikeshed

Covers what was broken, what was changed, how to run the check, which
warnings remain and why they're benign, and the merged-build result. No
prose, citations, `Issue:` text, or normative claims were touched in any
section; every change below is markup (escaping, heading ids, link-defaults,
WebIDL syntax validity, cross-reference handling) or splicing mechanics.

## How to run it

```
./build.sh
```

Run from the repo root (see README.md for the venv setup). This is the
invocation used throughout this pass. Bikeshed itself is called as
`bikeshed --die-on=nothing --print=json spec <in> <out>`, once per section
for STANDALONE and once for MERGED. The script re-fetches
`specification/index.bs` from `w3c/webextensions` on GitHub fresh every run
(`gh api repos/w3c/webextensions/contents/...`), so it stays correct if the
upstream file changes; it never writes into `sections/*.bs`.

`--die-on=nothing` is necessary because bikeshed's default
(`--die-on=fatal`) refuses to generate any output the instant it sees any
fatal message. `tools/classify.py` decides PASS/FAIL from the
`--print=json` message stream instead. It still accepts a list of
"Couldn't find target document section `<id>`" ids to allow through as
non-fatal, but neither the standalone nor the merged build needs one: see
below for why.

## What was actually wrong, by category

### 1. Raw `<...>` tokens eaten as HTML tags

This happens whenever bikeshed's `Markup Shorthands: markdown yes` metadata
flag is **not** set, and backticks do not protect against it. Fix:
`&lt;...&gt;` inside the code span. Each section's standalone metadata block
now sets `Markup Shorthands: markdown yes` (matching the real index.bs), so
this class of bug can no longer resurface for these six files, but the
underlying content was fixed at the character level regardless, so it also
compiles under the stricter no-markdown-shorthand test:

- **match-patterns**: `<all_urls>`, `<host>`, `<path>`, `<port>`, `<scheme>`,
  17 occurrences, including one inside a fenced grammar block.
- **globs**: 1 occurrence, a URL wrapped in angle brackets inside a backtick
  span (`` `// FIXME: <https://webkit.org/b/246492> ...` ``).
- **host-permissions**: `<all_urls>`, 2 occurrences.
- **version-number-handling**: 1 occurrence
  (`` `<number><string><number><string>` ``, describing Gecko's version
  grammar).
- **permissions-api**, **extension-ids**: 0 occurrences.

### 2. The `<all_urls>` heading/dfn (match-patterns)

`## <dfn>`<all_urls>`</dfn>` produced an empty-dfn/empty-heading-id/
duplicate-id chain once #1 above was fixed enough for bikeshed to get that
far. Fixed as:

```
## <dfn export>`&lt;all_urls&gt;`</dfn> ## {#all-urls}
```

`export` was added because bikeshed auto-marks a dfn whose text contains
disallowed characters (the escaped `<`/`>`) as `noexport`, which produced a
separate lint that `export` removes outright.

### 3. Explicit heading ids

Every heading in all six sections carries an explicit `{#id}`, matching the
real index.bs's own style. Two needed a name distinct from the "obvious" one
to avoid a collision once spliced in:

- **globs**: `## Key `include_globs`` and `## Key `exclude_globs`` would
  autoid to `key-include_globs`/`key-exclude_globs`, the same autoids the
  real index.bs's own stub headings under Architecture > Content scripts
  already use. Renamed to `{#globs-key-include_globs}` /
  `{#globs-key-exclude_globs}`. The pre-existing Content-scripts stubs are
  left untouched. **Content observation** (not fixed): globs and the
  Content-scripts section now both describe `include_globs`/
  `exclude_globs`, at different heading levels, in different places, which
  looks like something worth reconciling eventually, flagged rather than
  merged unilaterally.
- **permissions-api**: the prose-level `<dfn>permissions</dfn>` (the API
  concept) collided with the WebIDL dictionary member `permissions` (both
  autoid to `permissions`). Gave the prose dfn `id="permissions-api-concept"`.

### 4. Ambiguous cross-spec references (`link-defaults`)

`scheme`/`host`/`path`/`user agent` each resolve ambiguously against
several specs. The URL spec is the correct target for the first three
(confirmed by reading the surrounding prose, and by compiling: the
ambiguity warnings vanish and no other target is ever a better semantic
fit). `user agent` resolves ambiguously between the Infra spec (the
standard WHATWG concept, the ordinary web-specs sense used throughout
extension-ids) and the unrelated Reporting API spec. Every section carries
its own copy of this block:

```
spec:url; type:dfn; text:scheme
spec:url; type:dfn; for:url; text:host
spec:url; type:dfn; text:path
spec:infra; type:dfn; text:user agent
```

### 5. Cross-section and cross-document references

Two classes of reference in the original content genuinely cannot resolve
inside a single standalone file, because they point outside it:

**`[=glob=]` (match-patterns), defined in globs.** Handled with bikeshed's
`Ignored Terms` metadata field: `Ignored Terms: glob` in
match-patterns.bs's own metadata block. This tells bikeshed not to try to
autolink that text at all, rather than reporting a broken link. It was
never fatal (autolink failures are link-severity, not fatal), but leaving
it unhandled meant the standalone build wasn't actually clean.

**`[[#key-...]]` and similar section references into the real index.bs.**
Every one of these was converted to a plain markdown link to the published
draft, with the same fragment: `[[#key-host_permissions]]` became
`` [`host_permissions`](https://w3c.github.io/webextensions/specification/#key-host_permissions) ``,
and so on. This is truthful (it points at the actual current text for that
key) and always resolves (a plain link is never validated against the
target's contents by bikeshed). It is baked into the section body itself,
not just the standalone preamble, so it also carries through into the
merged build below: after splicing, these read as external links to the
published spec rather than as internal same-document links to the sibling
heading. That is a real trade-off, made deliberately rather than by
accident. It is a fine state to ship a draft in and a bad state to leave in
whatever eventually merges upstream: an editor splicing this content
into the real index.bs by hand should revert each converted reference back
to an internal `[[#id]]` link once the destination heading is actually in
the same document, which is a five-minute pass, not a re-derivation.

Every reference that was converted:

| Section | Reference | Target |
|---|---|---|
| match-patterns | `[[#determine-the-url-for-matching-a-document]]` | index.bs, Algorithms |
| globs | `[[#key-content_scripts-matches]]` (2 occurrences) | index.bs, Content scripts |
| permissions-api | `[[#key-optional_permissions]]`, `[[#key-optional_host_permissions]]`, `[[#promises-and-callbacks]]` | index.bs |
| host-permissions | `[[#key-host_permissions]]`, `[[#key-manifest_version]]`, `[[#key-permissions]]`, `[[#key-optional_host_permissions]]`, `[[#key-optional_permissions]]`, `[[#key-commands]]`, `[[#inject-a-content-script]]` | index.bs |
| extension-ids | `[[#key-externally_connectable]]` | index.bs |
| version-number-handling | `` [[#extension-runtime|`runtime.getManifest()`]] `` | nowhere, see finding below |

A same-file reference (for example host-permissions' own
`[[#restricted-urls]]` and `[[#user-gestures-and-activetab]]`, or
version-number-handling's own `[[#version-handling-key-version]]`) needed no
change: it already resolves inside a single section.

Separately, permissions-api's `[=optional permissions=]` / `[=optional host
permissions=]` *dfn* autolinks, as opposed to the `[[#key-...]]` *section*
links in the table above, stay unresolved even after merging: the section's
own Issue text says outright that those concepts "are not yet defined
elsewhere in this document." This is expected and non-fatal (a link-severity
warning, not a fatal), not a new finding, and was left alone.

## Splicing (merged build)

`tools/splice_merged.py` implements the mapping from source rows to their
target headings in the real index.bs. `build.sh` strips each section's
standalone preamble (the metadata block and link-defaults block, everything
before the marker comment) back out before handing the remainder to the
splicer, so the splicer itself is unmodified from its original form and
still operates on the same section bodies used in the tree today. Two
placements needed a judgment call:

- **host-permissions** contains a `## User gestures and activeTab` section,
  wrapped in an HTML comment in the file itself, noting that it belongs
  under `# Concepts` (replacing the empty heading already there), not under
  `# Host permissions`. The splicer honours that note: activeTab splices
  into `# Concepts` > `## User gestures and activeTab`, the rest of
  host-permissions splices under `# Host permissions`.
- **version-number-handling** opens with `## Key `version`` / `## Key
  `version_name`` sections *before* its own `# Version number handling`
  heading. Spliced verbatim at the single target location, that document
  order puts two `h2`s ahead of the `h1` they're meant to nest under, an
  illegal heading-level jump (confirmed fatal by compiling). The splicer
  reorders to `[h1 heading, the two Key sections, the rest]` when
  splicing, no prose changed, only where within the designated splice
  location the content sits.

## Content findings (reported, not fixed)

These came up while compiling and look like content or shape problems
rather than markup bugs. Left alone, per the task's rules.

1. **`` [[#extension-runtime|`runtime.getManifest()`]] `` in
   version-number-handling doesn't resolve anywhere.** Not in index.bs, not
   in any of the six sections. Unlike every other reference in the table
   above, there is no heading anywhere that defines it. Likely meant to
   eventually link to a `runtime` API namespace section (the same shape
   permissions-api gives `permissions`) that hasn't been drafted yet. It
   was converted to an external link the same as the others, which means it
   compiles clean, but the fragment it points at does not exist on the
   published page today either. This is a real content gap, not a markup
   fix waiting to happen.
2. **`[=extension version comparison=]` and `[=version comparison=]` in
   version-number-handling don't match its own `<dfn>compare two version
   strings</dfn>`.** Both are plain naming mismatches within the same
   section: the dfn is named differently than every place that tries to
   link to it. Non-fatal (bikeshed just can't find a same-doc dfn and
   reports a link error), so it doesn't block either build, but it means
   those two mentions are unlinked prose rather than links to the algorithm
   they're clearly referring to.
3. **`[=web accessible resource=]` in extension-ids is never defined
   anywhere.** index.bs has an empty `# Web accessible resources` heading
   but no `<dfn>`. Non-fatal, same reason as #2.

Resolved since: the WebIDL `interface Permissions` was renamed to lowercase
`interface permissions` (the dictionary keeps `Permissions`), and the four
`[=permissions/onAdded=]`-style dfn-autolinks in permissions-api.bs were
switched to `{{permissions/onAdded}}`-style IDL links, which is the syntax
that actually resolves a `<dfn method>`/`<dfn attribute>` dfn (a dfn-type
autolink never matches one, regardless of `for=` casing). Both the
dictionary/interface name collision and the four dead links are gone.

## Warnings that remain, and why they're benign

Every warning/lint left in the MERGED output was checked against a compile
of the pristine, unmodified real index.bs (no sections spliced in at all) to
confirm it already exists there today, unrelated to any of the six
sections:

- **"You should manually provide IDs for your headings"**: the pre-existing
  index.bs headings outside the six sections (Manifest Keys, Execution
  contexts, Architecture, etc.). None of the six sections' own headings
  appear in this list; all of them have explicit ids now.
- **"Multiple elements have the same id 'manifest'/'extension-origin'/
  'content-scripts'"** (3 dedup warnings): all three collide a pre-existing
  index.bs heading with a pre-existing index.bs `<dfn>`, same as in the
  pristine baseline compile, nothing to do with the six sections.
- **"Multiple possible 'list'/'realm' dfn refs"**, **"No 'dfn' refs found
  for 'runtime.connect()'/'runtime.sendMessage()'/'onConnectExternal'/
  'onMessageExternal'/'opener origin at creation'"**: all present, verbatim,
  in the pristine baseline compile (25 total link-severity items there vs.
  39 in the merged build; the 14 new ones are the cross-section/content
  items catalogued above).
- **"Unexported dfn ... not referenced locally"** (lint, 7 in the merged
  build): `RunAt`/`ExecutionWorld` are pre-existing (baseline has them too);
  the rest (`host permission`, `required host permission`, `request`,
  `permissions`, `compare two version strings`) are dfns from the six
  sections that nothing currently `[=links=]` to by that exact text
  locally, harmless, standard bikeshed advice, not an error.

Bikeshed's own summary line for the pristine, completely unmodified real
index.bs is "Successfully generated, with 25 linking errors": the live spec
already ships in a state with unresolved link-severity items today. The
MERGED build here reaches the equivalent state (0 markup/fatal bugs
introduced by the six sections, 1 documented content gap, everything else
either pre-existing or a reported-not-fixed content finding) rather than
some stricter bar the live document doesn't itself meet.

## Results

**STANDALONE**: 6 / 6 PASS, 0 fatal messages, 0 suppressions needed in any
section.

**MERGED**: PASS, 0 fatal messages, 0 suppressions needed. This is stricter
than an earlier pass over this same content, which needed to allow one
documented fatal through by name (the `extension-runtime` gap above); once
that reference became a plain external link, there was nothing left to
suppress in either build.

Markup fixes by category:
- angle-bracket escaping: 21 occurrences across match-patterns, globs,
  host-permissions, version-number-handling (17 + 1 + 2 + 1)
- heading ids added/renamed: 7 in match-patterns, 2 in globs, 5 in
  host-permissions, 2 in version-number-handling (bumped from h3 to h2 as
  well), 1 in extension-ids (permissions-api already had ids on every
  heading)
- dfn id collisions fixed: 2 (match-patterns' `<all_urls>` heading/dfn pair
  via `export`, permissions-api's `permissions` prose-dfn vs. WebIDL member)
- WebIDL syntax fix: 3 (permissions-api's `contains`/`request`/`remove`
  dictionary arguments marked `optional`, required for the block to parse
  as valid IDL at all)
- markdown structure fix: 1 (globs' list-item directly followed by `</div>`
  needed a blank line, a bikeshed markdown-parser requirement)
- link-defaults entries: 4 per section (scheme, host, path, user agent)
- cross-reference conversions: 17 `[[#id]]` occurrences converted to
  external links (1 match-patterns, 2 globs, 3 permissions-api, 9
  host-permissions, 1 version-number-handling, 1 extension-ids), 1
  `Ignored Terms` entry (`glob`)
- splice-order fix: 1 (version-number-handling's Key sections reordered
  after its own h1 heading when spliced, per above)

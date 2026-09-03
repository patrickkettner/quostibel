# quostibel

[![Build and deploy to Pages](https://github.com/patrickkettner/quostibel/actions/workflows/pages.yml/badge.svg)](https://github.com/patrickkettner/quostibel/actions/workflows/pages.yml)

Built pages: https://patrickkettner.github.io/quostibel/

## What This Is

Six draft sections for `w3c/webextensions`' `specification/index.bs`, the
WebExtensions specification. Each one is validated by reading the actual
Chromium, WebKit and Gecko source, not by reading documentation or a vendored
type package. Every claim in every section carries a file:line citation into
one of the three engines, in the matching file under `evidence/`.

## Three Corrections

These are the headline result, because they are errors in text already
published in the live `index.bs` today, not just gaps in it.

**Match patterns are not case-insensitive.** The spec currently says "They
are case-insensitive." That's true of the host component (folded, or
canonicalized to lowercase, depending on the engine) and false of the path
component. Path matching is case-sensitive in all three engines: Chromium,
Gecko, and WebKit all compare it byte-for-byte in their production code
paths.

**`?` does not match exactly one character.** The spec currently says it
does. That's Gecko's behavior. It isn't Chromium's: `base/strings/pattern.h`
states plainly that `?` matches 0 or 1 character, and
`EXPECT_TRUE(MatchPattern("", "?"))` in `pattern_unittest.cc` confirms it.
WebKit has no `?` semantics to compare, because it doesn't implement
`include_globs`/`exclude_globs` matching at all.

**"A glob can be any string" defines the syntax, not the behavior.** The
spec's current definition describes what a glob is allowed to look like,
which leaves open what a glob without any wildcard characters actually
does when matched. It matches only a URL identical to it; the definition
needs to say so.

## Status

Nothing here has been proposed to the WECG. Nothing has been filed anywhere,
against `w3c/webextensions` or against any engine's bug tracker. These are
drafts, meant for someone to read and argue with, not submissions.

## Sections

| Section | Description | Evidence | Engine agreement |
|---|---|---|---|
| [`sections/match-patterns.bs`](sections/match-patterns.bs) | Grammar and matching algorithm for match patterns, including `<all_urls>` | [`evidence/match-patterns.md`](evidence/match-patterns.md) | Core grammar agrees. 11 divergences, mostly at the edges: `<all_urls>` scheme coverage, `*` scheme expansion, ports, percent-decoding |
| [`sections/globs.bs`](sections/globs.bs) | `include_globs`/`exclude_globs` grammar and matching | [`evidence/globs.md`](evidence/globs.md) | Two engines, not three. WebKit implements neither `include_globs` nor `exclude_globs` |
| [`sections/permissions-api.bs`](sections/permissions-api.bs) | The `permissions` API namespace: `getAll`, `contains`, `request`, `remove`, `onAdded`, `onRemoved` | [`evidence/permissions-api.md`](evidence/permissions-api.md) | 5 of 6 members hold under source review. `request()` does not |
| [`sections/host-permissions.bs`](sections/host-permissions.bs) | Host permissions, restricted URLs, cross-origin fetch, `activeTab` | [`evidence/host-permissions.md`](evidence/host-permissions.md) | The core agrees: one access check gates content scripts, cookies, `webRequest`, and tab URLs in all three. Content-script CORS bypass is gone everywhere under MV3 |
| [`sections/version-number-handling.bs`](sections/version-number-handling.bs) | `version`/`version_name` keys, parsing, and comparison | [`evidence/version-number-handling.md`](evidence/version-number-handling.md) | Only Chromium validates format. Gecko accepts any string and warns. WebKit checks non-empty only |
| [`sections/extension-ids.bs`](sections/extension-ids.bs) | Uniqueness and derivation of extension IDs | [`evidence/extension-ids.md`](evidence/extension-ids.md) | Irreconcilable three ways by design: Chromium derives it from a key, Gecko takes it from the manifest, WebKit assigns it out of band |

## The Rest Of It

- [`burndown.md`](burndown.md): the six sections re-ranked by what the
  source actually showed, once each one was checked, against what looked
  right before any source was read.
- [`divergences.md`](divergences.md): every cross-engine divergence found,
  mapped against existing GitHub, Bugzilla, and WebKit bug threads, ranked by
  how tractable a fix looks.
- [`smaller-spec-units.md`](smaller-spec-units.md): smaller API surfaces
  (`storage.StorageChange`, `tabs.onRemoved`, and others) that look
  spec-able on their own, source-confirmed where noted.
- [`specability-analysis.md`](specability-analysis.md): which WebExtensions
  API namespaces are close enough to signature-identical across Chrome,
  Firefox, and Safari type data to be worth drafting from that data at all.

## How To Build

```
python3 -m venv bsvenv
bsvenv/bin/pip install bikeshed==7.1.2
bsvenv/bin/bikeshed update
./build.sh
```

`build.sh` compiles every file in `sections/` on its own, then splices all
six into a fresh copy of the real `index.bs` (fetched live via `gh api`, so
`gh` needs to be authenticated) and compiles that too. It reports pass or
fail per section, plus the merged result, and exits nonzero if anything
fails. See [`BUILD-NOTES.md`](BUILD-NOTES.md) for what makes a section
compile on its own when the real `index.bs` doesn't, and why.

## Open Items

Five content defects, found while getting the sections to compile and left
alone rather than fixed, because fixing them is an editorial decision, not a
markup fix:

1. `` `runtime.getManifest()` `` in version-number-handling links to a
   section (`extension-runtime`) that doesn't exist anywhere: not in
   `index.bs`, not in any of the six sections. It reads like it should point
   at a future `runtime` namespace section that hasn't been drafted yet.
2. `[=extension version comparison=]` and `[=version comparison=]` in
   version-number-handling don't match the actual dfn name,
   `compare two version strings`. Two mentions that should be links are
   unlinked prose instead.
3. `[=web accessible resource=]` in extension-ids is never defined anywhere.
   `index.bs` has an empty "Web accessible resources" heading and no dfn.
4. `dictionary Permissions` and `interface Permissions` share a name in
   permissions-api's WebIDL. Every `{{Permissions}}` reference in its prose
   resolves to a random one of the two on each build.
5. permissions-api's WebIDL uses `interface Permissions` as the `for`
   context on its method dfns, but host-permissions and permissions-api's
   own prose link as if there's a lowercase `permissions` namespace instead.
   Those links are currently dead.

Beyond that: several claims in the source material are marked undetermined
rather than guessed, because the trace ran out before a definite answer did.
Store-side enforcement of extension ID uniqueness (Chrome Web Store, AMO,
App Store Connect) isn't in any of the three read-only engine trees and
wasn't assessed. Whether Gecko decodes percent-encoded paths the way
Chromium does wasn't determined from `MatchPattern.cpp` alone. Whether a
managed/enterprise policy can make `permissions.request()` reject outright
in WebKit wasn't found in its extension API source, one way or the other.
Each `evidence/*.md` file states its own undetermined points explicitly
rather than rounding them up to a guess.

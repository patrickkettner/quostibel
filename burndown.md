# index.bs burndown

All six approved rows are drafted and validated against engine source: Chromium,
WebKit and Gecko. Every draft carries a findings file with file:line citations.
The sharpest claim in each row was re-checked by hand against the source.

Nothing has been sent to w3c/webextensions. Nothing has been filed anywhere.

## Two corrections to text already published in index.bs

These are the highest-value output. Both are errors in the current CG-DRAFT.

**Match patterns are not case-insensitive.** The spec says "They are
case-insensitive." Host is case-folded, path is not. Paths are case-sensitive in
all three engines.

**`?` does not match exactly one character.** The spec says it does. That is
Gecko's behavior only. Chromium's `base/strings/pattern.h:18` states "? matches
0 or 1 character", confirmed by `EXPECT_TRUE(MatchPattern("", "?"))` at
`pattern_unittest.cc:22`.

## Rows, re-ranked by what the source actually showed

| # | Row | Drafted | Engine agreement as found | Change from the pre-source ranking |
|---|---|---:|---|---|
| 1 | Match patterns | 231 lines | Core grammar agrees. 11 divergences, mostly at the edges: `<all_urls>` scheme coverage, `*` scheme expansion, ports, percent-decoding | Holds at the top. More divergences than expected, all writable as `Issue:` blocks |
| 2 | Globs | 30 lines | **Two engines, not three.** WebKit implements neither `include_globs` nor `exclude_globs` | Demoted. Four FIXMEs at webkit.org/b/246492 |
| 3 | `permissions` | 186 lines | 5 of 6 members hold under source review. `request()` does not | Holds. Still the strongest API candidate |
| 4 | Host permissions | 246 lines | The core agrees: one access check gates content scripts, cookies, webRequest and tab URLs in all three. Content-script CORS bypass is gone everywhere under MV3 | Holds. Better than expected |
| 5 | Version handling | 167 lines | Only Chromium validates format. Gecko accepts any string and warns. WebKit checks non-empty only | Specifiable as a conformance requirement, not as consensus |
| 6 | Extension IDs | 37 lines | Irreconcilable three ways by design | Demoted to defining the term plus normative minimums |

## Divergences worth a conversation with a specific team

Ordered by how actionable the conversation looks.

| Divergence | Outlier | Note |
|---|---|---|
| `include_globs` / `exclude_globs` unimplemented | WebKit | Thread already open at webkit.org/b/246492, four FIXMEs point at it |
| activeTab not revoked on navigation | Gecko | Its own source says "unlike Chrome, we don't currently clear this permission with the tab navigates". Known, deliberate, and security-relevant |
| No host permissions granted at install | WebKit | `WKWebExtensionContext.h:256` leaves all granting to the embedding app |
| Version component overflow clamped to 0 | Gecko | `"4294967295.0"` sorts newer than `"1.0"` in Chromium and older in Gecko. A real update can be an upgrade in Chrome and a downgrade in Firefox |
| `<all_urls>` covers a different scheme set | all three | No two agree. Genuinely open |
| `*` scheme expands differently | Gecko | http+https elsewhere, http+https+ws+wss in Gecko |
| Port syntax in patterns | all three | Supported in Chromium, silently unmatchable in Gecko, parse error in WebKit |
| `permissions.request()` reachable from content scripts | Firefox | Chromium and WebKit both exclude the whole namespace from content scripts |
| Origin host decoupled from extension ID | Gecko | Anti-fingerprinting, deliberate. Probably specify the difference rather than converge |

## Still open

- Row 3 left four items undetermined and they were left that way rather than
  inferred. Same for smaller sets in rows 1, 4, 5 and 6.
- Store-side ID uniqueness (Chrome Web Store, AMO, App Store) is not in any of
  these trees and was not assessed.
- Safari behavior beyond the generic `WKWebExtensionContext` API is application
  code not present in the open WebKit tree.
- Nothing here has been proposed to WECG. The mapping of each divergence onto
  threads that already exist is a separate pass.

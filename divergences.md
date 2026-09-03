# Cross-engine WebExtensions divergences mapped to existing conversations

Source findings: rows 1 (match patterns), 2 (globs), 3 (permissions API), 4 (host permissions /
activeTab / cross-origin fetch), 5 (version handling), 6 (extension IDs). All six rows are now
complete. Search performed 2026-09-03 against w3c/webextensions (GitHub issues, full-text and
label search), bugs.webkit.org, and bugzilla.mozilla.org. No issue, bug, or PR was filed,
commented on, or edited to produce this file; every existing-thread claim below was fetched and
quoted, not recalled.

## Summary table

| # | Divergence | Outlier | Existing thread | Tractability |
|---|---|---|---|---|
| 1 | `runtime.getVersion()` doesn't exist in Gecko | Gecko | w3c/webextensions #878 (CLOSED COMPLETED 2026-04-08); Firefox patch in progress, bugzilla.mozilla.org #1992418 | Very high: already agreed, fix is landing |
| 2 | `version_name` / `runtime.getVersionName()` gap in Gecko | Gecko (deliberate) | bugzilla #1380219 RESOLVED WONTFIX 2026-09-03; w3c/webextensions #1011 still OPEN but its premise is now false | Low: Mozilla has declined. Specify the difference, do not ask for convergence |
| 3 | WebKit never consults `include_globs`/`exclude_globs` | WebKit | bugs.webkit.org #246492 (NEW, dormant since 2024-04-22) | High: fix is named in-source with a FIXME |
| 4 | Match-pattern port syntax silently matches nothing | Gecko | bugzilla.mozilla.org #1468162 (UNCONFIRMED, dormant since 2021) | Medium: fix identified in 2018, then triaged away |
| 5 | **Gecko does not revoke `activeTab` on navigation** (security-relevant; source names Chrome) | Gecko | w3c/webextensions #55 (OPEN, dormant since 2021, zero comments) - but its factual claim about Firefox is the *opposite* of what current Gecko source says | Medium: thread exists but is dead and, per current source, wrong |
| 6 | Version-string grammar strictness (leading zeros, component bounds) | all three differ | w3c/webextensions #283 (OPEN, active 2026-06-21) and closed #1031 (folded into #283) | High: active WECG discussion, adjacent to #11 below |
| 7 | Spec text says path matching is case-insensitive; all three engines are case-sensitive | none (spec vs. reality) | none found | High: pure spec-text fix, zero engine work |
| 8 | WebKit's path-glob match target excludes the query string | WebKit | none found | Medium-high: source shows a single accessor swap |
| 9 | WebKit's `contains()` throws synchronously; `request()`/`remove()` reject, for the identical bad input | WebKit (internally) | none found | Medium: self-contained, low-risk fix inside one file |
| 10 | Gecko has no escape mechanism for `*`/`?` in globs; Chromium does | Gecko | none found | Medium: adds one case to an existing regex-building loop |
| 11 | **Version-comparison ordering flips**: `"4294967295.0"` sorts newer than `"1.0"` in Chromium, older (≈`"0.0"`) in Gecko, via silent int32-overflow clamp | Gecko | none found for the comparison bug itself (only the adjacent grammar thread, #6/#283) | Medium: narrow fix (stop clamping to 0 on overflow), but sibling bug #4 shows Mozilla has triaged a similar report away before |
| 12 | Glob `?` matches 0-or-1 chars (Chromium) vs. exactly 1 (Gecko) | 2-way (WebKit n/a) | none found | Medium: narrow, self-contained per engine |
| 13 | Glob match target includes the URL fragment (Chromium) vs. excludes it (Gecko) | Gecko (2-way, WebKit n/a) | none found | Low: small, edge-case fix |
| 14 | Chromium strips trailing dots from hosts before comparing; Gecko/WebKit unconfirmed | Chromium (only confirmed implementer) | none found | Low: minor, and 2 of 3 engines are unverified either way |
| 15 | `permissions.request()` reachable from content scripts | Firefox (deliberate) | none found | Low: looks like a considered Firefox design choice, not a bug |
| 16 | `permissions.getAll()` synthesizes an implicit all-hosts origin | WebKit | none found | Low-medium: looks deliberate (privacy/UX), not obviously wrong |
| 17 | `permissions.request()` requires a native window to exist | Chrome (deliberate) | none found | Low: looks like a considered Chrome UX check |
| 18 | Path percent-encoding: decode-and-compare (Chromium) vs. literal compare (WebKit) vs. undetermined (Gecko) | WebKit confirmed outlier, Gecko unknown | none found for match patterns (adjacent: w3c/webextensions #945, DNR only) | Medium: WebKit's half is a decode step; Gecko needs tracing first |
| 19 | Host-matching case sensitivity: deliberate (WebKit) vs. incidental (Chromium) vs. unknown (Gecko) | mixed / unclear | none found | Low: unclear what to even ask for until Gecko is traced |
| 20 | **WebKit grants no host permissions automatically at install**; Chromium and Gecko both auto-grant required `host_permissions` | WebKit | none found | Low tractability, high importance: an architectural choice (embedding app owns granting), not a bug |
| 21 | Restricted-host/domain lists differ in kind: Chromium blocks the Web Store domain + gates `chrome://`; Gecko blocks a configurable AMO/accounts allowlist + a separate quarantine list; WebKit has neither | all three differ in mechanism | none found | Low: policy-territory, WG may not want to standardize this at all |
| 22 | Content-script cross-origin fetch bypassed CORS under MV2 in Chromium (pre-Chrome-87) and Gecko (still shipping); unconfirmed whether WebKit's MV2 ever had it. All three agree for MV3 today. | historical / mostly resolved | adjacent: w3c/webextensions #730 (XHR/CSP inconsistencies, open, active 2024-12-06) - different mechanism, not the same finding | Low priority: largely already converged, FYI only |
| 23 | `<all_urls>` / bare `*` / ws-wss-data scheme coverage in match patterns | all three differ | none found (adjacent: w3c/webextensions #580, not the same conversation) | Low: deep, touches Chromium's permission-surface-specific scheme bitmasks |
| 24 | IDN/punycode canonicalization of the pattern's host at parse time | Chromium (only implementer) | none found | Low: real IDNA integration work for two engines, not an obvious "fix the bug" ask |
| 25 | `data_collection` permission dimension | Firefox only, pref-gated | none found | Low: not a bug fix, a whole missing concept for two engines |
| 26 | Enterprise/managed-policy blocking of optional permission requests | WebKit (unconfirmed absence) | none found | Unknown: absence isn't confirmed, so no fix can be sized yet |
| 27 | **Extension ID derivation is irreconcilable three ways**; Gecko deliberately decouples the origin host from the ID as an anti-fingerprinting measure | all three differ, Gecko's difference is intentional | none on w3c/webextensions; Mozilla-side #1717671 (NEW, active ~5 months ago) and meta-bug #1372288 push Gecko's decoupling *further*, not toward convergence | Lowest: this is a "specify the difference," not a "please converge" - Gecko's behavior is a considered privacy feature |
| 28 | `addHostAccessRequest`/`removeHostAccessRequest` (Chrome only); `AnyPermissions` (Firefox only) | Chrome and Firefox each carry a method/dictionary the other two lack | w3c/webextensions proposal `permissions-addHostAccessRequest-api.md`, PR #529/#728, #700 (closed, Safari opposed); minutes 2025-10-23 and 2025-03-26-berlin-f2f | Inventory difference, not a behavior mismatch on a shared member - out of scope for a cross-browser core spec by construction |

---

## 1. `runtime.getVersion()` doesn't exist in Gecko

**Outlier**: Gecko. Chromium's `getVersion()` returns the canonicalized `base::Version` string
(`extensions/renderer/api/runtime_hooks_delegate.cc:490-499`, `extensions/common/extension.cc:526-528`).
WebKit's returns the raw manifest string (no parsing exists to canonicalize).
A repo-wide grep for `getVersion` under `toolkit/components/extensions/` in Gecko finds nothing -
the method is not implemented for the `runtime` namespace at all (findings row 5, section 4).

**Existing conversation**: yes, and it's essentially resolved. **w3c/webextensions #878, "Proposal:
`runtime.getVersion()` method," closed 2026-04-08 as COMPLETED.** The final comment, from Mozilla's
`zombie`: "We have this implemented in two engines and already documented on MDN, so we don't need
to discuss it in this group. We have a patch for Firefox and should review/land it." The Firefox
patch is tracked at **bugzilla.mozilla.org #1992418** (cited directly in the body of the follow-on
issue #1011, see item 2). As of the tree read for this task, that patch had not yet landed - the
finding is accurate for the checked-out source, but the fix is already agreed and in flight, not
merely proposed.

**What harmony would look like**: Chrome and Safari already agree (`getVersion()` exists, both
shipped per xeenon's comment linking Safari Technology Preview 230); Gecko landing its patch
completes the convergence.

**Cost to the outlier**: minimal - a patch already exists and is awaiting review/landing per the
issue's own closing comment.

---

## 2. `version_name` / `runtime.getVersionName()` gap in Gecko

**Outlier**: Gecko. Chromium supports `version_name` as a pure display string, separate from the
comparable `version` (`extensions/common/manifest_handlers/version_name_info.cc:30-43`). WebKit
supports it identically, falling back to `version` when absent (`WebExtension.cpp:944-951`). Gecko
has no `version_name` manifest key at all; the only trace is a vestigial, never-populated
`versionName` field in the `management` API schema (findings row 5, section 5).

**Existing conversation**: yes, and it has been decided against. **bugzilla.mozilla.org #1380219,
"version_name key support in WebExtensions manifest.json," RESOLVED WONTFIX, last changed
2026-09-03.** Rob Wu, comment 7: "After a discussion with the broader add-ons team, we decided to
not implement version_name." The stated reasoning is that the version string is part of an add-on's
identity, that a customizable display string confuses users when they need to communicate which
version they are running, and that there is no clear benefit. **w3c/webextensions #1011** proposing
`runtime.getVersionName()` is still OPEN, but its premise no longer holds.

CORRECTION, 2026-09-03. An earlier revision of this document rated this "very high" tractability
and asserted that version_name "is being brought into Gecko as part of the same effort" as
`runtime.getVersion()`. That was an inference from #1011 citing bug 1992418, not something read
from a bug or from source, and it is false. Bug 1992418 ("Add runtime.getVersion()") is ASSIGNED
and genuinely in flight, which is item 1. It has nothing to do with version_name. The two were
conflated.

**What harmony would look like**: not convergence. Mozilla has given a reasoned decision, so the
spec should describe `version_name` as an optional key that implementations may ignore, and note
that a conforming implementation is not required to support it. Same shape as the extension ID
divergence at item 27: specify the difference rather than ask an engine to change.

**Cost to the outlier**: not applicable. This is not a gap to be closed, it is a design position.
The open question is whether w3c/webextensions #1011 should be closed or rescoped, since a
`getVersionName()` API cannot be implemented by an engine that has declined the manifest key it
reads.

---

## 3. WebKit never consults `include_globs`/`exclude_globs`

**Outlier**: WebKit, cleanly. Chromium and Gecko both implement glob matching (with their own
internal disagreements, see items 10, 12, 13). WebKit parses the manifest keys into
`includeGlobPatternStrings`/`excludeGlobPatternStrings` and then never reads them again anywhere
in `Source/WebKit` (findings row 2, section 6).

**Existing conversation**: yes, and WebKit's own source already names it. Both
`WebExtension.cpp:1322-1345` and `WebExtensionContext.cpp:1186-1207` carry the comment
`// FIXME: <https://webkit.org/b/246492> Add support for exclude globs.` and the matching
`include globs` line. Fetched directly: **bug 246492, "Support for globs in Web Extensions,"
component WebKit Extensions, status NEW, most recent activity 2024-04-22** (a comment noting the
missing `include_globs` support is compounded by `matches` not covering query strings; a
duplicate, bug 246613, was closed into this one in October 2022). As of today (2026-09-03) that's
just over two years of silence: not dead, but dormant enough that anything said there would be
reviving the thread, not restating it.

**What harmony would look like**: WebKit implementing the two keys the way Chromium and Gecko
already do (both engines agree glob matching should run at all; they only disagree on wildcard
details, which is items 10, 12, 13). Two engines already share the behavior "globs
restrict/exclude independently of `matches`" - WebKit should join them.

**Cost to the outlier**: the findings call out a second, independent bug in the same code path -
`WebExtension.cpp:1485,1494` filters globs with `!!value.asString().isEmpty()` instead of
`!value.asString().isEmpty()` (a copy-paste inversion versus every sibling filter in the file),
which currently discards every real glob string before the FIXME'd matching code would even see
it. Both the "add the matching" and the "fix the filter" pieces look self-contained: the parsing
and storage already exist, matching just needs to call into the same glob-testing primitive the
match-pattern code already uses.

---

## 4. Match-pattern port syntax silently matches nothing (Gecko)

**Outlier**: Gecko, and in the worst possible way - not a parse error, a pattern that always loses.
Chromium treats a port as real grammar (parsed, defaults to "any," enforced when explicit).
WebKit treats a port in the pattern as a hard parse error (`Error::InvalidHost`). Gecko's
host-parsing loop never looks for a `:` separator at all, so `http://mozilla.org:8080/` becomes a
literal domain string `"mozilla.org:8080"` that can never equal a real (portless) `nsIURI` host
(findings row 1, section 2, "Ports"; `test_MatchPattern.js:118,120`).

**Existing conversation**: yes. **bugzilla.mozilla.org #1468162, "Ports in match patterns match no
URLs," status UNCONFIRMED**, filed 2018-06-05, root cause identified the same day
("MatchPattern.cpp... has no mention of looking at the port"), last activity 2021-08-30 (an
automated severity adjustment; the last human comment was 2021-07-21, setting priority P5). Five
years silent from the last human touch as of today. The bug's whiteboard already carries a note
that a design change here was declined once.

**What harmony would look like**: Chromium's behavior (parse the port, default to "any," enforce
when explicit) is the only one of the three that does anything useful with a port an author
writes; WebKit's reject-at-parse-time is at least honest about not supporting it. Gecko's
"silently becomes unmatchable" is strictly worse than either - it is the one behavior no author
could have intended.

**Cost to the outlier**: the fix location was already named by a Mozilla engineer in 2018
(`MatchPattern.cpp`'s host-parsing loop, `MatchPattern.cpp:285-331` in the current tree). The
question isn't fix size, it's that Mozilla already declined to prioritize it once (P5, 2021); a
new conversation here is "please reconsider," not "please notice this."

---

## 5. Gecko does not revoke `activeTab` on navigation (security-relevant)

**Outlier**: Gecko, and the divergence is named in Gecko's own source. Chromium's
`ActiveTabPermissionGranter` clears the grant on `DidFinishNavigation()` whenever the navigation
is a committed, cross-document, primary-main-frame, **cross-origin** navigation
(`active_tab_permission_granter.cc:242-259`). WebKit's `clearUserGesture()` is called whenever the
committed URL no longer matches the granted temporary match pattern
(`WebExtensionContextCocoa.mm:1639-1642,2321-2331`) - functionally close to Chromium's model.
Gecko's `addActiveTabPermission` ties the grant to the *inner window* surviving, including bfcache
revival, not to same-origin-vs-cross-origin navigation, and the source says so directly:

> `toolkit/components/extensions/parent/ext-tabs-base.js:2184-2187`: "Note that, unlike Chrome, we
> don't currently clear this permission with the tab navigates. If the inner window is revived
> from BFCache before we've granted this permission to a new inner window, the extension maintains
> its permissions for it."

Verified directly against the checked-out tree at this exact location - the comment is real and
current. Gecko's `activeTab` grant is instead revoked only by `revokeActiveTabPermission()`, called
when a *different* toolbar action is invoked on the tab, not by navigation
(`ext-tabs-base.js:2199-2201`). This is security-relevant, not merely a compatibility gap: a page
that navigates the granted tab to new content (same window, no toolbar-action re-trigger) can end
up running under a still-live `activeTab` grant in Firefox where Chrome and Safari would have
revoked it.

**Existing conversation**: a thread exists, but it is old, dead, and - on its face - describes the
opposite of what the current source shows. **w3c/webextensions #55, "Inconsistent behavior of
`activeTab` on refresh/navigation across browsers," open, most recently active 2021-08-10, zero
comments.** Its body states: "Firefox: this access is lost after the first http navigation/refresh."
That is the reverse of the Gecko source comment quoted above, which says explicitly that Gecko does
*not* clear the permission on navigation. Two explanations are possible and this task cannot
distinguish them from source alone: either Gecko's behavior changed since mid-2021 (the source
comment carries no bug number or date to check against), or the original issue's author had it
backwards from the start; either way, nobody ever corrected the issue (zero comments in five
years), so its factual claim should not be trusted as a description of Gecko's current behavior.
No separate Mozilla-specific bugzilla bug was found describing the bfcache/navigation-retention
behavior itself (multiple targeted searches for "activeTab," "bfcache," "navigation," "not
cleared" against bugzilla.mozilla.org returned only unrelated activeTab bugs).

**What harmony would look like**: Chromium and WebKit agree activeTab should be revoked when the
tab navigates away from the origin it was granted for; that is the majority position and the more
conservative, least-surprising one for a temporary, gesture-scoped permission. Gecko's bfcache
carve-out reads as a real behavioral choice (preserving the grant across a bfcache-revived
document rather than a genuinely new page), but as written it also covers ordinary same-document
navigation within the tab, which is broader than "bfcache" alone.

**Cost to the outlier**: not sizeable from the two files read for this task - `activeTabWindowID`
is compared against `innerWindowID` at check time (`ext-tabs-base.js:212-217`), so tying revocation
to navigation would mean adding a navigation-observer call to `revokeActiveTabPermission()`
alongside the existing action-invocation call site; this looks self-contained but was not traced
further into Gecko's navigation-event plumbing.

---

## 6. Version-string grammar strictness (leading zeros, component bounds)

**Outlier**: all three differ, in the shape of the disagreement rather than a clean 2-vs-1 split.
Chromium: 1-4 components, each `0`-`4294967295`, leading zeros rejected only in the first
component (elsewhere tolerated with a canonicalization warning). Gecko: up to 4 components
recommended but unlimited actually accepted, any leading-zero shape only warns, never rejects.
WebKit: no grammar validation at all beyond non-empty (findings row 5, section 1).

**Existing conversation**: yes, open and recently active. **w3c/webextensions #283, "Spec
clarification (minor): handling of version strings with leading zeros in browser UI and stores,"
open, most recently active 2026-06-21**, labeled `inconsistency`, `spec clarification`, `next
manifest version`, with `needs-triage` on all three vendors. A companion issue, **#1031, "Disallow
leading zeros in next manifest version," closed 2026-06-19** as duplicate/folded into #283. Recent
comment thread (2026-06-21) explicitly discusses phasing out leading-zero tolerance in a future
manifest version, with a Mozilla-side comment ("we may want to consider making the version
stricter in mv4... to make sure `getVersion()` gives same results cross browser") directly tying
this to item 1's `getVersion()` effort.

**What harmony would look like**: SemVer's "no leading zeros" rule is cited approvingly in the
issue itself and is the strictest of the three engines' actual behavior, so the direction of travel
already visible in the thread (tighten toward Chromium's stricter grammar, phased in at a manifest
version boundary) looks like the emerging consensus, not an open question.

**Cost to the outlier**: this is squarely a "future manifest version" change per the thread's own
`next manifest version` label - not urgent, and explicitly framed as non-breaking for existing
manifest versions.

---

## 7. Spec text claims case-insensitive path matching; all three engines are case-sensitive

**Outlier**: none - this is a divergence between the target document and reality, not between
engines. All three engines compare the path component case-sensitively in production (findings
row 1, section 3, citing `url_pattern_unittest.cc:1358-1397`'s separate opt-in
`case_sensitive=false` mode that no Chromium call site actually uses;
`test_MatchPattern.js:495-496` for Gecko; a plain `==` in WebKit's `MatchTester`). The document's
"They are case-insensitive" line is accurate only for WebKit's *host*/*scheme* comparisons, not
for path matching in any engine.

**Existing conversation**: none found (searched "case-insensitive," "case sensitive path,"
"match pattern spec case," "index.bs match pattern" against w3c/webextensions).

**What harmony would look like**: this isn't a "which engine wins" question - it's a documentation
correction to match what all three engines already do. No engine needs to change.

**Cost to the outlier**: zero engine cost; it's a spec-text edit.

---

## 8. WebKit's glob match target excludes the query string

**Outlier**: WebKit. Chromium matches globs against `url.spec()` (scheme, authority, path, query,
fragment). Gecko matches against the URL spec with only the fragment stripped (still includes the
query string). WebKit's `matchesPath()` calls `URL::path()` specifically, a distinct accessor from
`URL::query()`, and no call to `query()` appears anywhere in `UserContentURLPattern.cpp` (findings
row 1, section 2, "Query string"). This is flagged in the findings as inferred from which accessor
is called, not confirmed by an executed test with a literal `?` separator.

**Existing conversation**: none found. Note for context, not a substitute: MDN's cross-vendor
"Match patterns" reference documents the Chromium/Gecko behavior ("path matches against the URL
path plus query string, including the `?`") as the norm, which is independent, non-source
corroboration that the two-engine behavior is the one documented as expected - but MDN is not a
conversation with WebKit, and this claim was pulled from web search, not verified as citing
WebKit's own tests.

**What harmony would look like**: the behavior Chromium and Gecko already share (path+query, no
fragment) is the natural target, since MDN already documents it as the cross-browser expectation.

**Cost to the outlier**: per the source read, this looks like changing one accessor call to
combine `path()` and `query()` - but the findings explicitly flag that no test in
`WKWebExtensionMatchPattern.mm` exercises a literal unescaped `?` end-to-end, so the actual
behavior (as opposed to what the source implies) isn't proven; that's the first thing any
conversation would need to nail down.

---

## 9. WebKit's own three functions disagree on error shape for a bad permission string

**Outlier**: WebKit, against itself. `contains()` throws synchronously
(`[RaisesException]`, `WebExtensionAPIPermissionsCocoa.mm:66-83,230-250`) for an unrecognized
permission name, while `request()` and `remove()` route the identical validation failure through
`callback->reportError(...)` (a promise rejection) instead, with an explicit comment: "Chrome
reports this error as callback error and not an exception, so do the same"
(`WebExtensionAPIPermissionsCocoa.mm:98-101,132-136`) - i.e. WebKit consciously chose to match
Chrome for two of the three functions and left the third inconsistent.

**Existing conversation**: none found.

**What harmony would look like**: WebKit's own comment already states the intended target
(match Chrome's reject-not-throw behavior); `contains()` is the one function left out of that
alignment. This is arguably a WebKit-internal bug report rather than a three-way spec
conversation, since WebKit's own code says what it meant to do.

**Cost to the outlier**: looks small and self-contained - same file, same
`validatePermissionsDetails()` call already shared by all three functions; only the error-reporting
call at the end of `contains()` diverges.

---

## 10. Gecko has no escape mechanism for `*`/`?` in globs

**Outlier**: Gecko. Chromium's `base::MatchPattern` treats `\` as an escape character for the next
character, letting an author write a literal `*` or `?` in a glob
(`pattern_unittest.cc:19`, `He??o\*1*`). Gecko's glob-to-regex compiler has no such case: its
`metaChars` escaping (`MatchPattern.cpp:767`) exists only to keep regex-special characters from
corrupting the built-in regex, and treats `\` itself as just another regex-special character to
escape, never as an escape operator in the glob syntax (findings row 2, section 2). There is
consequently no way to write a literal `*` or `?` in a Gecko `include_globs`/`exclude_globs` entry.

**Existing conversation**: none found (WebKit n/a per item 3).

**What harmony would look like**: adopt Chromium's backslash-escape convention, since it is a pure
capability gap in Gecko rather than a case where the two behaviors conflict - an author who never
needs a literal `*`/`?` sees no difference.

**Cost to the outlier**: the findings show the exact insertion point -
`MatchPattern.cpp:769-796`'s three-way `if` (`*` / `?` / "everything else") would need a fourth
case recognizing `\` followed by `*` or `?`. Self-contained to that constructor.

---

## 11. Version-comparison ordering flips on int32 overflow (Chromium vs. Gecko)

**Outlier**: Gecko, and the divergence is a live correctness bug, not a style question. Both
strings below are accepted as valid by both engines, and both engines order them oppositely.

- Chromium parses `"4294967295.0"`'s first component as the literal `uint32_t` value
  `4294967295` (`UINT32_MAX`) and orders it **greater than** `"1.0"`
  (`base/version.cc:61-86`).
- Gecko's `ParseVP` calls `strtol` successfully, but the result is narrowed through
  `CheckedInt<int32_t>`; `4294967295` exceeds `INT32_MAX` (`2147483647`), so the narrowing fails
  and the value is **silently replaced with `0`** (`nsVersionComparator.cpp:47-68,62-67`). Gecko
  therefore orders `"4294967295.0"` as equal to `"0.0"`, i.e. **less than** `"1.0"`.

Confirmed source-side by the findings, not hypothetical: this is a real string a manifest author
(or an attacker crafting a malicious update) could write, accepted by both engines' parsers, that
Chromium treats as a huge version jump forward and Gecko treats as a downgrade to zero. This has
a real consequence for update logic: Gecko's own `XPIInstall.sys.mjs:4342` rejects an install that
isn't strictly newer than an already-installed add-on of the same ID via this exact comparator, so
a version string engineered to hit this overflow could behave unpredictably in an update-gating
decision.

**Existing conversation**: none found for the comparison bug itself. The adjacent thread, #283/
#1031 (item 6), discusses version-string *grammar* strictness (should leading zeros or unbounded
component counts be allowed at all) but at no point mentions the comparison algorithm's int32
narrowing or this specific ordering flip - it is a different question with a shared cause (Gecko's
looser acceptance of large numeric components).

**What harmony would look like**: Chromium's plain, unbounded numeric-tuple comparison is the
straightforwardly correct behavior here; Gecko's silent clamp-to-zero on overflow is a bug by any
reasonable definition (the alternative reading, "reject the value," is what Gecko does everywhere
else it can't represent a number - it does not do that here, it substitutes zero without warning).

**Cost to the outlier**: narrow in isolation - `nsVersionComparator.cpp:47-68`'s overflow branch
would need to stop silently substituting `0`. But bug #4 (item 4, port matching) is a caution: a
prior source-identified, narrowly-scoped fix report in this same file's problem space was
triaged to P5 and left for years. A conversation here should expect the same friction unless it's
framed around the security angle (a malicious or malformed version string reordering itself past
update checks), which #4's report did not have available to it.

---

## 12. Glob `?` matches 0-or-1 characters (Chromium) vs. exactly 1 (Gecko)

**Outlier**: 2-way disagreement; WebKit doesn't implement globs at all (item 3), so this is
Chromium vs. Gecko, not a 3-way split. Chromium's `EatWildcards` treats a run of `?`s as an upper
bound on how many characters can be skipped, so a lone `?` matches the empty string too
(`pattern_unittest.cc:22`, `MatchPattern("", "?")` is true; `:26-27` shows three `?` cannot span 4
characters). Gecko compiles `?` straight to regex `.` - exactly one character, unconditionally
(findings row 2, section 1).

**Existing conversation**: none found ("wildcard question mark glob" and "escape backslash"
returned nothing on w3c/webextensions).

**What harmony would look like**: genuinely open rather than a clear winner. Chromium's "0 or 1"
reading is arguably surprising for a character conventionally understood as "exactly one" (shell
and regex conventions both treat a single wildcard char as exactly-one); Gecko's is the more
intuitive reading. But the target document's current text ("`?` matches exactly one character")
matches Gecko and contradicts Chromium, so at minimum the document is wrong for one of its two
implementers - this needs a decision, not just a doc fix.

**Cost to the outlier (whichever side moves)**: small either direction - it's a single character
class inside each engine's existing glob compiler.

---

## 13. Glob match target includes the fragment (Chromium) vs. excludes it (Gecko)

**Outlier**: Gecko (2-way; WebKit n/a). Chromium matches against `url.spec()` unmodified, fragment
included. Gecko explicitly strips the fragment via `NS_GetURIWithoutRef` before taking the spec
(findings row 2, section 3). A glob like `*#section` can match in Chromium and can never match in
Gecko.

**Existing conversation**: none found.

**What harmony would look like**: this is a narrower, more clearly-scoped version of the query-string
question in item 8 - genuinely open which is "correct" (fragments are client-side-only and
arguably shouldn't gate script injection, which would favor Gecko's stripping; but consistency
with Chromium's simpler "the whole spec" rule is also defensible).

**Cost to the outlier**: small either direction - one call site, `URINoRef()` vs. the un-stripped
URI, in Gecko's `CSpec()`.

---

## 14. Chromium strips trailing dots from hosts; Gecko/WebKit unconfirmed

**Outlier**: Chromium is the only *confirmed* implementer of trailing-dot stripping
(`url_pattern.cc:129-132`, `CanonicalizeHostForMatching`, tested by
`url_pattern_unittest.cc:967-1005`). The findings explicitly could not confirm whether Gecko's
`MatchesDomain` or WebKit's `matchesHost` do or don't strip a trailing dot - no stripping call was
found in either, but neither is exercised by a test in either engine's suite for this case.

**Existing conversation**: none found ("trailing dot" surfaced only DNR-normalization issue #770,
a different subsystem).

**What harmony would look like**: undetermined pending confirmation in the other two engines; not
enough is known yet to say who the outlier even is, only that Chromium is the one engine known to
normalize this.

**Cost to the outlier**: not assessable from source alone in Gecko/WebKit's case; would need
either a build or a positive test showing `example.com.` behavior in each.

---

## 15. `permissions.request()` reachable from content scripts (Firefox only)

**Outlier**: Firefox, deliberately. Chrome scopes the entire `permissions` namespace to
`"contexts": ["privileged_extension"]`
(`chrome/common/extensions/api/_api_features.json:810-819`), confirmed reachable-by-ordinary-
extension by the findings' own reachability-graph tool with no allowlist gate. WebKit marks the
whole `WebExtensionAPIPermissions` IDL interface `MainWorldOnly`, which is false for any
content-script isolated world. Firefox's schema instead sets
`"allowedContexts": ["content"]` on `request()` specifically, leaving the other four functions on
the namespace's default (privileged) contexts (findings row 3, section 2, "Called from a content
script").

**Existing conversation**: none found.

**What harmony would look like**: Chrome and WebKit agree the whole namespace is
extension-page-only; that's the majority position. But Firefox's carve-out is narrow and
deliberate (only `request()`, not the whole namespace), which is a different shape of decision
than a bug - it reads as an intentional content-script ergonomics choice, not an oversight.

**Cost to the outlier**: not a "fix," a design question - removing it is a capability regression
for whatever content-script use case motivated the `allowedContexts` override in the first place
(not identified in the files read for this task).

---

## 16. `permissions.getAll()` synthesizes an implicit all-hosts origin (WebKit only)

**Outlier**: WebKit. Chrome and Firefox agree `getAll()` returns exactly the union of required
manifest permissions and granted optional/runtime permissions - no more, no less (findings row 3,
section 4, `permissions_api.cc:202-206` and `Extension.sys.mjs:1388-1411`). WebKit does that same
union, but additionally appends the all-hosts-and-schemes match pattern to `origins` whenever
granted access effectively covers all hosts even though no literal all-hosts pattern was ever
declared (e.g. broad access assembled implicitly via `tabs`/`webNavigation`-style grants)
(`WebExtensionContextAPIPermissionsCocoa.mm:70-84`).

**Existing conversation**: none found.

**What harmony would look like**: Chrome and Firefox's narrower, technically-exact reporting is
the shared behavior; but the findings note WebKit's synthesis has a plausible purpose (surfacing
the true scope of access rather than a literal-but-misleading narrower set) - this reads as a
considered choice, so the conversation is "why," not "please fix."

**Cost to the outlier**: not sized - this is a "should this be spec'd as intentional or reverted"
question, not a code-size question.

---

## 17. `permissions.request()` requires a native window to exist (Chrome only)

**Outlier**: Chrome. `GetNativeWindowForUI()` is checked independently of the user-gesture check
and errors with "Could not find an active window" if none exists
(`permissions_api.cc:325-329`). Neither WebKit (which times out silently after 2 minutes if the
embedding app's delegate never responds, `WebExtensionContextCocoa.mm:113,751-756`) nor Firefox
(whose prompt goes out as an observer notification with whatever browser element is available,
`ext-permissions.js:189-205`) has an equivalent hard error.

**Existing conversation**: none found.

**What harmony would look like**: this is a UX/reliability tradeoff, not a correctness bug - Chrome
fails fast and explicitly; WebKit fails slow and silently (2-minute timeout); Firefox doesn't fail
at all if no window is available. None of the three is obviously wrong; a shared answer would need
to pick between "fail fast," "fail slow," and "don't fail."

**Cost to the outlier**: not applicable in the "fix a bug" sense - Chrome's behavior looks
intentional.

---

## 18. Path percent-encoding: decode-and-compare (Chromium) vs. literal (WebKit) vs. undetermined (Gecko)

**Outlier**: WebKit confirmed; Gecko's behavior is explicitly unconfirmed in the findings (no
explicit unescape call found in `MatchPattern.cpp`, but whether `nsIURI`'s stored path is already
decoded upstream was not traced - flagged "not determined" rather than "matches Chromium" or
"matches WebKit"). Chromium tries both the unescaped-UTF8 and raw forms
(`url_pattern.cc:590-684`); WebKit compares the literal, possibly percent-encoded string with no
decoding at all, proven directly by `WKWebExtensionMatchPattern.mm:398-400` (a pattern with a
literal `%3F` only matches a URL with the identical literal `%3F`).

**Existing conversation**: not for match patterns. **w3c/webextensions #945, "DNR URL matching and
percent encoding," open, most recently active 2026-01-29**, is the adjacent precedent - same three
engines, same theme, but scoped to `declarativeNetRequest` `urlFilter` matching, a different
subsystem from `content_scripts.matches`/`host_permissions` path matching. Worth citing as
evidence the working group already tracks percent-encoding divergences elsewhere, not as the same
conversation.

**What harmony would look like**: not decidable yet with two of three engines' behavior only
partly known (Gecko undetermined). Chromium's "try both forms" is the most permissive/forgiving
and would be the most natural target if Gecko turns out to already decode.

**Cost to the outlier**: WebKit's half looks like a real decode step would need to be added, not
just adjusted, since it decodes nothing today. Gecko's status can't be sized without first tracing
`nsStandardURL`.

---

## 19. Host-matching case sensitivity: deliberate (WebKit) vs. incidental (Chromium) vs. unknown (Gecko)

**Outlier**: mixed, not clean. WebKit calls `equalIgnoringASCIICase`/`endsWithIgnoringASCIICase`
explicitly (`UserContentURLPattern.cpp:224-247`) - deliberately case-insensitive regardless of how
the pattern was written. Chromium's host comparison is case-insensitive only as a side effect of
both sides already being canonicalized to lowercase before the `==`
(`url_pattern.cc:514-546`) - an intentionally-uppercase pattern host would still work today, but
not because of a fold. Gecko has no case-folding call anywhere in `MatchesDomain`
(`MatchPattern.cpp:372-386`), which the findings flag as "inferred from source, not directly
tested" - an uppercase pattern host may not match a real (lowercase) URL host in Gecko.

**Existing conversation**: none found.

**What harmony would look like**: not decidable as stated - Gecko's actual behavior needs
confirming (a build or a positive test) before there's a real three-way comparison to reconcile.

**Cost to the outlier**: not sized; contingent on the Gecko finding above.

---

## 20. WebKit grants no host permissions automatically at install

**Outlier**: WebKit, and this is a large behavioral gap, not a narrow one. Chromium auto-grants
required `host_permissions` at install and separately supports runtime withholding on top of that
default grant (`ScriptingPermissionsModifier`, `extensions/browser/permissions/
scripting_permissions_modifier.h:46-73`). Gecko likewise treats required host permissions as
granted, subject to its own MV3 OriginControls per-site downgrade system
(`ExtensionPermissions.sys.mjs:605-736`). WebKit has **no engine-level auto-grant at all**. The
public header states this outright:

> `Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionContext.h:256-257`: "Permissions in this
> dictionary should be explicitly granted by the user before being added" (for
> `grantedPermissions`; identical language at lines 266-268 for `grantedPermissionMatchPatterns`).

`WebExtensionContext::load()` (`WebExtensionContextCocoa.mm:276-338`) grants nothing; it only
reads back whatever was previously persisted (`readStateFromStorage()`, line 294). The embedding
native app (Safari, or any other WKWebExtension-based browser) is entirely responsible for
presenting the manifest's required permissions and populating `grantedPermissions`/
`grantedPermissionMatchPatterns` itself; nothing in the engine forces this to happen at install
(findings row 4, section 3).

**Existing conversation**: none found (searched w3c/webextensions for "auto-grant," "install host
permissions grant," "Safari host permissions," "grantedPermissions," "required permissions granted
at install" - all empty or unrelated).

**What harmony would look like**: this is less "who's right" than "who owns the decision." Chromium
and Gecko agree the *browser* auto-grants required host permissions and lets the user downgrade
afterward; WebKit inverts the responsibility entirely to the embedding app, with no engine-level
default at all. A spec that only describes what Chromium and Gecko already share would be
describing something WebKit's architecture doesn't have a slot for - this looks like a case where
the spec would need to describe the app-delegated model as a legitimate alternative, not treat
WebKit as needing to catch up.

**Cost to the outlier**: not a small patch - it's the shape of WebKit's whole permission-request
architecture (the embedding app is the trust boundary, not the engine). Changing it to auto-grant
at the engine level would be a platform design change, not a bug fix, and would need Safari/App
Store review-flow buy-in, which is outside the open-source WebKit tree read for this task.

---

## 21. Restricted-host/domain lists differ in kind

**Outlier**: none cleanly - the three engines protect different things, differently. Chromium
unconditionally blocks scripting of the Chrome Web Store domains
(`extension_urls.cc:41-42,145-147`) and gates `chrome://` scheme access behind a flag, with zero
permitted chrome-scheme hosts for MV3 extensions regardless of flags
(`chrome_extensions_client.cc:129-141`). Gecko blocks a configurable pref-based allowlist of AMO
and Firefox-accounts domains (`extensions.webextensions.restrictedDomains`,
`all.js:3133`) plus a separately-configurable quarantine list that privileged extensions can be
exempted from (`WebExtensionPolicy.h:139-146`). WebKit has no equivalent restricted-domain list
found anywhere under `Source/WebKit/UIProcess/Extensions/` or `Source/WebKit/Shared/Extensions/` -
the findings flag this as an absence-based, unconfirmed finding, plausibly explained by Safari
extensions being distributed through App Store review rather than a web-reachable gallery a
content script could target (findings row 4, section 5).

**Existing conversation**: none found.

**What harmony would look like**: genuinely unclear whether this belongs in a WebExtensions spec at
all - the findings themselves note this is enterprise/store-policy territory the working group may
deliberately choose not to standardize, since Chromium's Web Store block and Gecko's AMO allowlist
each protect a specific commercial distribution surface that has no WebKit analog to protect.

**Cost to the outlier**: not applicable in a "fix WebKit" sense, since WebKit may have nothing
equivalent to protect; more a question of whether the spec should even have a normative section
here.

---

## 22. Content-script cross-origin fetch: historical MV2 divergence, converged for MV3

**Outlier**: historical, and now largely resolved. Chromium removed content-script CORS bypass
starting Chrome 73 (CORB), completed in Chrome 85 (CORS), and fully removed the allowlist in
Chrome 87 - a platform change that predates MV3 and applies uniformly today. Gecko's source
comments show the same end state reached differently: content-script `fetch`/`XMLHttpRequest`/
`WebSocket` are pushed as sandbox globals bound to the extension's principal *only* under MV2
(`ExtensionContent.sys.mjs:1063-1074`, with an explicit `isMV2` branch); under MV3 those globals
are not pushed, so content-script fetch runs under the page's own principal - matching Chromium's
already-shipped model. WebKit ties its CORS-disabling `WKWebViewConfiguration` exclusively to
extension pages, never to the content-script `WKWebView`; whether WebKit's content-script fetch
ever bypassed CORS under an MV2-era mode could not be confirmed or denied from source (a negative
finding, findings row 4, section 2).

**Existing conversation**: not the same finding, but adjacent: **w3c/webextensions #730, "XHR from
content scripts should not be affected by page's CSP / Permissions-Policy (also, cross-browser
inconsistencies)," open, most recently active 2024-12-06.** That thread is about a different
mechanism - synchronous XHR being blocked by `Permissions-Policy: sync-xhr` in Chrome vs. `CSP
connect-src` in Firefox for MV3 content scripts - not about the historical CORS-bypass-removal
question this finding covers.

**What harmony would look like**: for MV3, all three already agree (content scripts get no CORS
bypass); nothing to reconcile there. The only open point is confirming WebKit's MV2-era behavior,
which is a factual gap, not a disagreement to resolve.

**Cost to the outlier**: not applicable - this is FYI/completeness, not a live three-way gap.

---

## 23. `<all_urls>` / bare `*` / ws-wss-data scheme coverage in match patterns

**Outlier**: all three, and the findings call this "the single largest three-way divergence."
Chromium's `<all_urls>` width is context-dependent (6-8 schemes depending on whether the caller is
`content_scripts.matches` or `host_permissions`, never `data:`). Gecko's is one fixed 7-scheme set
including `data:`. WebKit's is a fixed ~3-scheme set (http, https, its own extension scheme),
excludes `file:` by default, and never includes ftp/ws/wss/data. The same three-way split repeats
for the bare `*` scheme wildcard (Chromium+WebKit: http+https only; Gecko: http+https+ws+wss) and
for general ws/wss/data support (Chromium: ws/wss for `host_permissions` only, never `data:`;
Gecko: both, unconditionally; WebKit: neither) (findings row 1, sections 2 and 4).

**Existing conversation**: not the same conversation, but adjacent. **w3c/webextensions #580,
"Proposal: Match pattern matches," open, most recently active 2025-03-21**, proposes an API to
check whether a URL matches a pattern; comments there already surface pieces of this exact
divergence in passing (a commenter linking to fregante's `webext-patterns` package notes matching
is "browser- and context-dependent," and another comment references WebKit's own narrower
`Options` dictionary for scheme handling), but the issue itself is about adding a checking API, not
about reconciling the scheme sets. No issue found that is actually scoped to "what should
`<all_urls>`/`*` expand to."

**What harmony would look like**: no clean two-against-one here even at the sub-question level
(Chromium's own answer varies by call site). This is the kind of question the findings flag as
needing "let us specify the difference" framing rather than "please fix" - there may be no single
right answer, only a decision about how wide to standardize.

**Cost to the outlier**: deep for all three, differently. Chromium's width is threaded through
which caller-supplied bitmask reaches the parser (`extension.cc:217-221` vs.
`user_script.cc:67-73`), not a single constant. WebKit's narrowness is tied to its
`registerCustomURLScheme` runtime-registration mechanism. Gecko's fixed set is the simplest to
change but reconciling it with the others means picking a side in a debate none of the three has
resolved internally.

---

## 24. IDN/punycode canonicalization of the pattern's host at parse time (Chromium only)

**Outlier**: Chromium, as the only implementer, not the odd one out in a 2-vs-1 sense. Chromium
calls `net::CanonicalizeHost()` on the pattern's host at parse time, so a Unicode host in the
pattern text matches both Unicode and punycode forms of a real URL
(`url_pattern.cc:332-341`, `url_pattern_unittest.cc:1072-1108`). Neither Gecko nor WebKit make any
IDNA/ACE call; a Unicode-literal pattern host would only match a real (already-punycode) URL host
if the extension author wrote the punycode form themselves (findings row 1, section 2, "IDN /
punycode" - flagged as inferred from the absence of a normalization call, not from a passing/
failing test, for both Gecko and WebKit).

**Existing conversation**: none found (also checked Mozilla bugzilla directly; the closest hits
were unrelated IDN-display bugs and a `moz-extension:` scheme-support bug, not this).

**What harmony would look like**: Chromium's behavior is more permissive and arguably more
correct (it lets an author write the host the way they'd naturally read it), but "more permissive"
isn't automatically "the standard" - this is a case where the minority behavior could be the one
worth adopting, which the findings anticipated as a possibility.

**Cost to the outlier**: real work for both Gecko and WebKit - adding IDNA/ACE normalization to a
URL-matching path that has never had it, not a small patch.

---

## 25. `data_collection` permission dimension (Firefox only, pref-gated)

**Outlier**: Firefox. Its `Permissions`/`AnyPermissions` dictionaries carry a third member,
`data_collection: array<manifest.OptionalDataCollectionPermission>`
(`permissions.json:26-31,55-60`), gated behind
`extensions.dataCollectionPermissions.enabled` (default `false`,
`ext-permissions.js:19-24,41-46`). Neither Chrome's schema nor WebKit's IDL declares any such
field (findings row 3, sections 1, 3, 6).

**Existing conversation**: none found.

**What harmony would look like**: not a "fix a divergence" question - Chrome and WebKit don't have
the concept of a distinct data-collection permission at all, so this is a feature-parity gap, not
a behavior mismatch on a shared concept.

**Cost to the outlier**: not applicable to Firefox (it's the one with the feature); for Chrome/
WebKit, adopting it means designing a whole new permission category, well beyond a bug fix.

---

## 26. Enterprise/managed-policy blocking of optional permission requests (WebKit, unconfirmed)

**Outlier**: possibly WebKit, but not confirmed. Chrome has an explicit
`kBlockedByEnterprisePolicy` check (`permissions_api.cc:406-410`). Firefox has an explicit
equivalent check against `Services.policies?.getExtensionSettings(...)?.blocked_permissions`, with
a comment noting it matches Chrome's error string on purpose (`ext-permissions.js:150-165`). The
two WebKit files that implement `permissionsRequest()` show no such check, but the findings
explicitly flag this as "undetermined whether WebKit enforces managed configuration... through some
other layer not read for this task" - grepped only within `Source/WebKit/*/Extensions`.

**Existing conversation**: none found (web search for WebKit enterprise/managed permission
handling surfaced only Firefox-side results).

**What harmony would look like**: can't be stated yet - if WebKit does enforce this elsewhere (an
MDM profile mechanism was named as a plausible location but not checked), there's no divergence
to reconcile at all.

**Cost to the outlier**: not sizeable until the absence is actually confirmed. This should be the
first thing verified, not the first thing raised with a vendor.

---

## 27. Extension ID derivation is irreconcilable three ways

**Outlier**: all three, by design, and one of the three differences is a deliberate privacy
feature rather than an accident. The three engines don't just format IDs differently - they
derive them from entirely different inputs:

- **Chromium**: the ID is a hash. `GenerateId()` takes the first 16 bytes of `SHA256` of the
  developer's packaging public key and hex-encodes them through an `a`-`p` alphabet (chosen
  specifically so an all-numeric ID is never mistaken for an IP host,
  `components/crx_file/id_util.cc:21-57`). Unpacked/dev-mode loads without a key instead hash the
  extension's absolute load path (`extension.cc:172-179`), explicitly to keep the ID stable across
  reloads. **The origin host literally is the ID** (`extension.cc:447-458`).
- **Gecko**: the ID is author-declared text in the manifest
  (`browser_specific_settings.gecko.id`, a GUID-in-braces or an email-like string,
  `XPIInstall.sys.mjs:489-491`), not derived from anything cryptographic. Critically, **the origin
  host is deliberately *not* the ID** - it's a separate, machine-and-profile-specific random UUID,
  generated once per (profile, extension-ID) pair and persisted in a pref. The source states the
  reason outright:

  > `toolkit/components/extensions/Extension.sys.mjs:361-366`: "All moz-extension URIs use a
  > machine-specific UUID rather than the extension's own ID in the host component. This makes it
  > more difficult for web pages to detect whether a user has a given add-on installed (by trying
  > to load a moz-extension URI referring to a web_accessible_resource from the extension)."

  Verified directly in the checked-out tree. `browser.runtime.id` still returns the manifest ID,
  not the UUID (`ext-runtime.js:133`) - so the ID an extension sees about itself and the host a web
  page can observe are two different, deliberately-decoupled values.
- **WebKit**: the ID (`uniqueIdentifier`) is neither cryptographic nor manifest-declared. It
  defaults to a freshly-generated random UUIDv4 on every `WebExtensionContext` construction
  (`WebExtensionContext.h:1095`) and is stable only if the embedding app explicitly calls
  `setUniqueIdentifier()` with a value it persists itself before each load
  (`WebExtensionContext.cpp:154-165`). By default the origin host equals the identifier, but both
  are independently settable public API properties (`WKWebExtensionContext.h:179-195`), so WebKit
  doesn't even have a fixed relationship between "ID" and "origin host" the way the other two do.

**Existing conversation**: nothing on w3c/webextensions scoped to this three-way derivation
question (searched "extension id," "extension origin host," "moz-extension uuid," "fingerprint
extension" - no hits). On the Mozilla side, the relevant threads push Gecko's decoupling *further*,
not toward convergence: **bugzilla.mozilla.org #1717671, "Avoid the use of a persistent UUID in the
public base URL of extensions," status NEW, most recently updated ~5 months ago** (a whiteboard
edit), proposes reducing the UUID's scope/lifetime even more, because the current persistent UUID
is itself now understood to be a fingerprinting vector once leaked via a shared
`web_accessible_resource`. The meta-bug **#1372288, "[meta] WebExtensions can be used as user
fingerprint,"** frames the whole area. Neither thread is a conversation with Chromium or WebKit
about aligning ID derivation - they are Gecko strengthening its own model.

**What harmony would look like**: per the brief for this item, this should not be pitched as
"please converge." Chromium's origin-host-is-the-ID model is the one Gecko's own source explicitly
argues against on privacy grounds, and Gecko is actively working to decouple further, not less.
WebKit's app-assigned-UUID model is a third, unrelated axis (trust delegated to the embedding app,
same shape as its host-permissions model in item 20). The only thing that unifies all three is
that `browser.runtime.id`/`chrome.runtime.id` returns *some* string extension code can rely on as
stable-within-its-own-scope - the derivation, format, and relationship to the origin host are
genuinely different design decisions, not implementation bugs. A spec conversation here is well
framed as "specify that the three engines derive and scope the ID differently, and specify what
invariants extension authors can actually rely on" (e.g., can code assume `runtime.id` is stable
across restarts? across profiles? does the origin host equal the ID?) - not "which one is right."

**Cost to convergence, if it were attempted (not recommended)**: total, for at least two of the
three engines. Chromium would have to give up ID-equals-key-hash (its entire update/CRX
verification model is keyed on this, `crx_verifier.cc:166-208`). Gecko would have to give up the
anti-fingerprinting host indirection its own source calls out as intentional. This is presented
here as evidence the divergence is structural, not as a proposal to change either engine.

---

## Items deliberately not written up as their own conversation

Per the source findings' own recommendation, these were found but are not drafted as standalone
divergences: IPv6 bracket-vs-stripped host storage (not expected to be externally observable);
Gecko's `aExplicit` early-rejection of subdomain-wildcard patterns (a permission-classification
behavior layered on top of match-pattern matching, not core grammar, with no located counterpart
in the other two engines to compare against); whether an empty `include_globs: []` in a manifest's
`content_scripts` entry normalizes to "omitted" in Gecko the way it's documented to for the
`userScripts` runtime API (a Gecko-internal open question, not a cross-engine divergence, since
Chromium's behavior on this exact point is already known and Gecko's own runtime-API behavior
already matches it - only the manifest-key code path is untraced); and the fine-grained
"explicit" vs. "implicit" permission-grant distinctions inside Gecko's and WebKit's host-permission
state machines (enum shapes confirmed, not traced to every call site, per findings row 4 section 5
note 2).

## Resolution: WECG #55 was wrong from the day it was filed

The open question left above was whether Gecko's behavior changed since 2021 or
whether w3c/webextensions#55 was wrong at the time. It was wrong at the time.

`git blame` dates the Gecko comment "unlike Chrome, we don't currently clear
this permission with the tab navigates"
(toolkit/components/extensions/parent/ext-tabs-base.js:2184) to 2017-01-30,
Kris Maglione. Issue #55 was filed 2021-08-06, four years later, asserting the
opposite. It has zero comments and was last touched 2021-08-10. Still OPEN.

The surrounding code was last modified 2022-08-16 by Tomislav Jovanovic, who is
one of the four editors of specification/index.bs.

This makes #55 the most actionable item in this document: the contribution is
correcting a stated premise with a dated source citation, not arguing for a
behavior change.

## 28. `addHostAccessRequest`/`removeHostAccessRequest` (Chrome only); `AnyPermissions` (Firefox only)

**Outlier**: Chrome and Firefox each add a member the other two engines don't have. Chrome's
`permissions.json` declares `addHostAccessRequest`/`removeHostAccessRequest`, methods that let an
extension ask the browser to surface its own "request access to this site" toolbar UI rather than
prompting through `permissions.request()`. Firefox declares a separate `AnyPermissions`
dictionary, used only by `getAll()`/`contains()`, distinct from the `Permissions` dictionary used
by `request()`/`remove()`/the events; its only difference from `Permissions` is the
`data_collection` member (see item 25).

**Existing conversation**: `addHostAccessRequest` was designed collaboratively in the WECG before
Chrome shipped it (`proposals/permissions-addHostAccessRequest-api.md`, referenced from PR
#529/#728). Issue #700 (closed) recorded Safari's position against adding it. Minutes
2025-10-23-wecg.md and 2025-03-26-berlin-f2f.md both discuss whether it should extend to
Firefox; Safari's non-participation is treated as settled, not open.

**What harmony would look like**: not applicable to this specification. Both are cases of one
engine having an extra method or dictionary member the others lack entirely, which is an
inventory difference rather than a behavior mismatch on a member all three implement - out of
scope for a spec that defines the cross-browser core.

**Cost to the outlier**: n/a - this is a scoping note, not a fix request.

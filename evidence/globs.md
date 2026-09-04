# Globs: three-way source findings

Trees read (all read-only, no build):
- Chromium: `extensions/`, `base/strings/`
- Gecko: `toolkit/components/extensions/`
- WebKit: `Source/WebKit/UIProcess/Extensions/`

Current index.bs text (fetched via `gh api repos/w3c/webextensions/contents/specification/index.bs`, saved as `index.bs.orig` in this directory), `# Globs` heading, line 254-256:

> A glob can be any string. It can contain any number of wildcards where `*` can match zero or more characters and `?` matches exactly one character.

That sentence was added by [w3c/webextensions#542](https://github.com/w3c/webextensions/pull/542),
"Add content scripts section in specification." The pull request's own body calls the section
"a first draft," and its author asked reviewers directly, "Would you be able to take a look at
this one and confirm if it is accurate? This was my best understanding based on bugs and
documentation in the code." Nobody confirmed it in the PR thread, and no other discussion of
`?` semantics was found anywhere in the group's record: it was never checked against source,
not merely wrong.

The "inject a content script" algorithm, line 397-411, currently states this order:
1. `url` matched against `matches` (else return)
2. If `include_globs` present, `url` must match a glob in it (else return)
3. If `url` matches `exclude_matches` or `exclude_globs`, return
4. child-frame / `all_frames` check
5. inject

---

## 1. Wildcard semantics

### Chromium
`extensions/common/user_script.cc:34-43` (`UrlMatchesGlobs`) calls `base::MatchPattern(url.spec(), glob)` for each glob (`base/strings/pattern.h:19-20`). The header comment (`base/strings/pattern.h:16-18`) says explicitly:

> The backslash character (\) is an escape character for * and ?.
> ? matches 0 or 1 character, while * matches 0 or more characters.

This is not a documentation simplification; the implementation matches it exactly. `EatWildcards` (`base/strings/pattern.cc:96-112`) scans a run of consecutive `*`/`?`: if the run contains at least one `*` the run is unbounded (`-1`, i.e. matches any number of characters); if the run is `?` only, it returns the *count* of `?`s, which becomes `maximum_distance` in `SearchForChars` (`pattern.cc:20-90`). `SearchForChars` tries to match the next literal subpattern starting at offsets `0, 1, 2, ... maximum_distance` in the input, i.e. a run of k consecutive `?` characters matches between 0 and k characters, not exactly k.

Verified directly by `base/strings/pattern_unittest.cc`:
- line 22: `EXPECT_TRUE(MatchPattern("", "?"));` -- a lone `?` matches the empty string, i.e. zero characters.
- line 26/27: `EXPECT_TRUE(MatchPattern("abcd", "*???"))` but `EXPECT_FALSE(MatchPattern("abcd", "???"))` -- three bare `?` cannot span a 4-character string (max span is 0-3), confirming the "up to k" semantics.
- line 16: `EXPECT_TRUE(MatchPattern("Hello", "H?l?o"));` -- ordinary single-`?` case reads as "exactly one" here only because the alternative (zero chars) would not produce a full match; it does not contradict the 0-or-1 finding.

`*` in Chromium matches zero or more of any character, including `/` (no path-segment special-casing appears anywhere in `pattern.cc`; `www.google.com` matches `*.com`, `pattern_unittest.cc:13`, and a full URL spec containing multiple `/` is matched with a plain `*`, `user_script.cc:37`).

### Gecko
`toolkit/components/extensions/MatchGlob.cpp` (implementation lives in `MatchPattern.cpp:743-807`, class declared in `MatchGlob.h:25-55`). `MatchGlobCore`'s constructor (`MatchPattern.cpp:747-801`) compiles the glob to a regular expression (`RustRegex`) when it isn't a pure literal or `foo*` prefix pattern:

```
MatchPattern.cpp:786-790
    if (c == '*') {
      if (!emittedFirstStar) {
        escaped.AppendLiteral(".*");
        ...
    } else if (c == '?' && aAllowQuestion) {
      escaped.Append('.');
```

So `*` becomes regex `.*` (zero or more of any character -- `.` in this regex engine is not newline-matching but URLs never contain a literal newline, so this is immaterial; it does match `/`), and `?` becomes regex `.` -- exactly one character, unconditionally (a bare `?` cannot match zero characters). `aAllowQuestion` is `true` for `include_globs`/`exclude_globs` (see below), so `?` is always treated as a wildcard for content-script globs.

This is a real, source-confirmed divergence from Chromium: Gecko's `?` matches exactly one character; Chromium's `?` matches zero or one.

### WebKit
Not applicable -- WebKit does not implement glob matching at all (see section 6). There is no wildcard semantics to report because the parsed glob strings are never compiled or evaluated against a URL.

### Verdict on the sentence currently in index.bs
"`?` matches exactly one character" is correct for Gecko and incorrect for Chromium, where a bare `?` matches zero or one character (confirmed by `pattern_unittest.cc:22`, `MatchPattern("", "?")` is true). It is moot for WebKit since the keys are parsed but never consulted. The sentence needs to say the two engines disagree, not state one behavior as if both share it.

---

## 2. Escaping

### Chromium
Yes. `base/strings/pattern.cc:47-53`, inside `SearchForChars`:
```
if (!escape && **pattern == '\\') {
  escape = true;
  next(pattern, pattern_end);
  continue;
}
```
A backslash consumes the following character literally (suppressing wildcard interpretation for that one character). Verified by `pattern_unittest.cc:19`: `EXPECT_TRUE(MatchPattern("Hello*1234", "He??o\\*1*"));` -- the pattern `He??o\*1*` contains a literal `\*` that must match the literal `*` in `Hello*1234`.

### Gecko
No escape mechanism exists. In the regex-building loop (`MatchPattern.cpp:769-796`), the only three cases are: `*` (wildcard), `?` (wildcard, if allowed), and "everything else" -- the "everything else" branch checks a fixed `metaChars` set (`.+*?^${}()|[]\`, `MatchPattern.cpp:767`) and if the character is one of those, prefixes it with a backslash before appending it to the built regex, purely so it is not misinterpreted as regex syntax. `\` (backslash) is itself in `metaChars`, so a literal backslash in the glob is regex-escaped to a literal backslash in the resulting expression -- it is never treated as an escape character for `*` or `?` in the glob syntax itself. There is no code path anywhere in `MatchGlobCore`'s constructor that special-cases a `\*` or `\?` sequence in the input glob.

Consequence: Gecko provides no way to write a literal `*` or `?` in an `include_globs`/`exclude_globs` entry. They are always wildcards.

### WebKit
Not applicable (unimplemented).

---

## 3. What the glob is matched against

### Chromium
`url.spec()` -- the full serialized URL, unmodified. `extensions/common/user_script.cc:37`:
```
if (base::MatchPattern(url.spec(), glob)) {
```
`GURL::spec()` includes scheme, authority, path, query string, and fragment.

### Gecko
`aURL.CSpec()`, called from `WebExtensionPolicy.cpp:1010-1011` and `:1032` (`mIncludeGlobs.Value().Matches(aURL.CSpec())`, `mExcludeGlobs.Value().Matches(aURL.CSpec())`). `URLInfo::CSpec()` (`MatchPattern.cpp:161-166`):
```
const nsCString& URLInfo::CSpec() const {
  if (mCSpec.IsEmpty()) {
    (void)URINoRef()->GetSpec(mCSpec);
  }
  return mCSpec;
}
```
`URINoRef()` (`MatchPattern.cpp:175-181`) explicitly strips the URL fragment via `NS_GetURIWithoutRef` before the spec is taken. Gecko's glob match target is the full URL spec with scheme, authority, path, and query, but without the `#fragment`.

This is a genuine divergence from Chromium's `url.spec()`, which includes the fragment. A glob such as `*#section` would be able to match in Chromium but can never match in Gecko, because the fragment is not part of the string Gecko tests against.

### WebKit
Not applicable (unimplemented) -- there is no code path that decides what string a glob would be matched against.

---

## 4. Case sensitivity

### Chromium
Case-sensitive. `base::MatchPattern` does raw UTF-8/UTF-16 codepoint comparison in `SearchForChars` (`pattern.cc:61-70`) with no case folding anywhere in the file. Verified: `pattern_unittest.cc:18`, `EXPECT_FALSE(MatchPattern("www.msn.com", "*.COM"));`.

### Gecko
Case-sensitive. `MatchGlobCore::Matches` (`MatchPattern.cpp:809-816`) does plain `nsCString` equality (`mPathLiteral == aString`) or `RustRegex::IsMatch` with a pattern that is never given a case-insensitive flag; no `ToLowerASCII`/`ToLowerCase` call appears anywhere in `MatchPattern.cpp` (grepped, zero hits).

Both implementing engines agree: glob matching is case-sensitive, in contrast to match patterns, which index.bs already documents as case-insensitive (line 253, "A match pattern... They are case-insensitive.").

### WebKit
Not applicable (unimplemented).

---

## 5. Empty glob list / empty-string glob

### Chromium
An empty `globs_` vector (whether `include_globs`/`exclude_globs` was omitted from the manifest, or explicitly written as `[]` -- Chromium's parsing, `extensions/common/utils/content_script_utils.cc:389-401` `ParseGlobs`, does not distinguish the two; it just appends whatever strings are present) is treated as "no restriction." `extensions/common/user_script.cc:230-231`:
```
return (url_set_.is_empty() || url_set_.MatchesURL(url)) &&
       (globs_.empty() || UrlMatchesGlobs(&globs_, url));
```
`globs_.empty()` short-circuits to true. An empty glob list matches everything (it imposes no additional filter).

A single empty-string glob (`[""]`) is different: `MatchPattern(url_spec, "")` is only true when `url_spec` itself is empty (`pattern_unittest.cc:24`, `EXPECT_FALSE(MatchPattern("Hello", ""));`), which a real URL spec never is. So `[""]` effectively matches nothing.

### Gecko
For the `browser.userScripts.register`/`update` JS API, an explicit `includeGlobs: []`/`excludeGlobs: []` is documented and tested as equivalent to omitting the field, matching Chromium: `toolkit/components/extensions/test/xpcshell/test_ext_userScripts_mv3_persistence.js:180-183`:
```
// matches or includeGlobs must be non-empty, we cannot use [] here.
...
includeGlobs: [],
excludeGlobs: [],
...
// An input of [] is equivalent to omitted, which is returned as null.
// Chrome does the same.
```
That normalization is applied before the value reaches the C++ `Nullable<MatchGlobSet>` (`WebExtensionContentScript.h:189-190`); at the C++ level, if `mIncludeGlobs` were non-null but held an empty set, `MatchGlobSet::Matches` (`MatchPattern.cpp:858-865`, empty loop, returns `false`) combined with `WebExtensionPolicy.cpp:1010-1011` (`!mIncludeGlobs.IsNull() && !mIncludeGlobs.Value().Matches(...)`) would make the script match nothing -- the opposite of Chromium. The JS-level `[] -> null` normalization is what prevents that outcome for the tested API.

Resolved: the `[] -> omitted` normalization does NOT apply on the `manifest.json` `content_scripts` key path, and an explicit `"include_globs": []` there produces the opposite of Chromium's behavior. The two paths are not the same code:

- `toolkit/components/extensions/schemas/manifest.json`'s `ContentScript` definition (`include_globs`/`exclude_globs`, around lines 802-811) and `schemas/user_scripts.json`'s `includeGlobs`/`excludeGlobs` (lines 67-76, 144-153) are schema-identical: both are a plain optional `array` of `string` with no `minItems`, so the JSON Schema layer itself does not coerce or reject `[]` on either path; whatever happens is decided entirely by the JS code downstream of schema validation.
- The `userScripts` runtime API explicitly normalizes: `ExtensionUserScripts.sys.mjs:592` defines `const nonEmptyOrNull = arr => (arr?.length ? arr : null);`, applied to `includeGlobs`/`excludeGlobs` at `ExtensionUserScripts.sys.mjs:608-613`. This is what turns `[]` into `null` before construction.
- `Extension.sys.mjs:2158-2159` (the `content_scripts` manifest path) has no equivalent call: `includeGlobs: options.include_globs` passes the value through unchanged, so an explicit `"include_globs": []` in the manifest stays a literal empty array all the way to construction.
- `dom/chrome-webidl/WebExtensionContentScript.webidl:126,128` declares `sequence<MatchGlobOrString>? includeGlobs = null;` (and the same for `excludeGlobs`): a nullable sequence whose *default*, when the property is absent, is `null`. But WebIDL does not treat a JS `[]` as equivalent to `null`; a literal empty array is bound as a present-but-empty sequence, not coerced to the default.
- `WebExtensionPolicy.cpp:845-847`: `if (!aInit.mIncludeGlobs.IsNull()) { ParseGlobs(...); mIncludeGlobs.SetValue(...); }`. A present-but-empty sequence takes this branch (`IsNull()` is false), so `mIncludeGlobs` ends up set to a non-null, empty `MatchGlobSet` -- not left null.
- At match time, `WebExtensionPolicy.cpp:1009-1011`: `if (!mIncludeGlobs.IsNull() && !mIncludeGlobs.Value().Matches(aURL.CSpec())) { ...fail... }`. For a non-null but empty set, `Matches()` returns `false` (confirmed above, `MatchPattern.cpp:858-865`), so the negation is `true` and the match fails unconditionally.

Net effect: `"content_scripts": [{"matches": [...], "include_globs": []}]` in a Gecko manifest makes the content script match no URL at all, the opposite of Chromium's "no restriction" for the identical input, and the opposite of what Gecko's own `userScripts` API does for the same `[]` value on `includeGlobs` -- because only the `userScripts` path carries the explicit `nonEmptyOrNull` normalization. This is a real, source-confirmed within-Gecko inconsistency between its two content-script-registration surfaces, not merely an unconfirmed absence.

A single empty-string glob in Gecko: `MatchGlobCore`'s constructor finds no wildcard char (`FindCharInSet` returns `-1` for an empty string, `MatchPattern.cpp:751-754`), so `mPathLiteral = ""` and matching falls to `mPathLiteral == aString` (`MatchPattern.cpp:809-816`), true only when the matched string is itself empty. Same conclusion as Chromium: matches nothing against a real URL.

### WebKit
Not applicable (unimplemented).

---

## 6. Interaction and precedence with match patterns

index.bs's current algorithm order (line 397-411): `matches` -> `include_globs` -> (`exclude_matches` or `exclude_globs`) -> `all_frames` -> inject.

### Chromium
`UserScript::MatchesURL` (`extensions/common/user_script.cc:215-231`):
```
bool UserScript::MatchesURL(const GURL& url) const {
  if (!exclude_url_set_.is_empty() && exclude_url_set_.MatchesURL(url)) return false;
  if (!exclude_globs_.empty() && UrlMatchesGlobs(&exclude_globs_, url)) return false;
  if (GetSource() == UserScript::Source::kDynamicUserScript) {
    return (url_set_.MatchesURL(url) || UrlMatchesGlobs(&globs_, url));
  }
  return (url_set_.is_empty() || url_set_.MatchesURL(url)) &&
         (globs_.empty() || UrlMatchesGlobs(&globs_, url));
}
```
Checks `exclude_matches`, then `exclude_globs`, then `matches` AND `include_globs` (for ordinary, manifest-declared content scripts). The check order is reversed relative to index.bs's stated order, but the underlying boolean formula is a pure conjunction of independent, side-effect-free predicates, so the result is identical regardless of evaluation order; there is no behavioral divergence from reordering alone. Note also: for dynamic user scripts (the `chrome.userScripts` API's `Source::kDynamicUserScript`, not the `content_scripts` manifest key that index.bs's algorithm documents), the relationship is `matches` OR `include_globs`, not AND. This OR case is out of scope for the "Inject a content script" algorithm as currently scoped to manifest content scripts, but worth flagging if the glob spec text intends to also cover `userScripts.register`.

### Gecko
`MozDocumentMatcher::MatchesURI` (`WebExtensionPolicy.cpp:1005-1032`) checks `matches` AND `include_globs` first (or OR for `mIsUserScript`, mirroring Chromium's dynamic-user-script OR case), then `exclude_matches`, then `exclude_globs`. This order matches index.bs's stated order more closely than Chromium's does, but again, since all four predicates are independent and side-effect-free, this is not an observable behavioral difference from Chromium -- just a different source-code check order for the same boolean result.

### WebKit
Does not implement `include_globs` or `exclude_globs` matching at all. The manifest keys are parsed (`Source/WebKit/UIProcess/Extensions/WebExtension.cpp:1481-1494`) into `InjectedContentData.includeGlobPatternStrings`/`excludeGlobPatternStrings` (`WebExtension.h:189-190`), but grepping the entire `Source/WebKit` tree for these two field names turns up no other reference anywhere -- they are written once and never read.

The two functions that actually decide whether a content script matches a URL both contain an explicit acknowledgment that globs are unimplemented:

`WebExtension.cpp:1322-1345` (`WebExtension::hasStaticInjectedContentForURL`):
```
bool WebExtension::hasStaticInjectedContentForURL(const URL& url)
{
    ...
    for (auto& injectedContent : m_staticInjectedContents) {
        // FIXME: <https://webkit.org/b/246492> Add support for exclude globs.
        bool isExcluded = false;
        for (auto& excludeMatchPattern : injectedContent.excludeMatchPatterns) {
            if (excludeMatchPattern->matchesURL(url)) { isExcluded = true; break; }
        }
        if (isExcluded) continue;
        // FIXME: <https://webkit.org/b/246492> Add support for include globs.
        for (auto& includeMatchPattern : injectedContent.includeMatchPatterns) {
            if (includeMatchPattern->matchesURL(url)) return true;
        }
    }
    return false;
}
```
`WebExtensionContext.cpp:1186-1207` (`WebExtensionContext::hasInjectedContentForURL`) is structurally identical, with the same two `FIXME: <https://webkit.org/b/246492>` comments.

So in WebKit, matching for a content script that declares `include_globs`/`exclude_globs` reduces to `matches` AND NOT `exclude_matches` only -- the glob keys are silently ignored. An extension author who relies on `include_globs` to narrow a broad `matches` pattern will see the script injected into a broader set of URLs in WebKit-based Safari than in Chrome or Firefox; an author relying on `exclude_globs` to carve out an exception will see the script injected where they expected it to be excluded.

As a secondary, independent finding: the manifest-parsing step for these two keys (`WebExtension.cpp:1485`, `:1494`) itself has an inverted filter predicate:
```
includeGlobPatternStrings = filterObjects(*includeGlobPatternStrings, [](auto& value) {
    return !!value.asString().isEmpty();
});
```
`filterObjects` keeps array elements for which the lambda returns `true` (`Source/WebKit/Shared/Extensions/WebExtensionUtilities.cpp:35-48`). Every other caller of `filterObjects` in this file (e.g. `scriptPaths`, `styleSheetPaths`, `excludeMatchesArray`-adjacent filtering) uses `!value.asString().isEmpty()` to keep non-empty strings -- the correct sense for "drop blank entries." The two glob filters instead use `!!value.asString().isEmpty()`, which is logically identical to `value.asString().isEmpty()` and keeps only empty strings, discarding every real glob pattern an extension author wrote. This looks like a copy-paste bug (missing negation) independent of the FIXME above, but it is moot in practice since `includeGlobPatternStrings`/`excludeGlobPatternStrings` are never read downstream regardless of what they contain.

---

## Summary table

| Question | Chromium | Gecko | WebKit |
|---|---|---|---|
| `*` semantics | 0+ of any char, incl. `/` | 0+ of any char, incl. `/` | n/a (unimplemented) |
| `?` semantics | 0 or 1 char | exactly 1 char | n/a |
| Escaping | `\` escapes next char | none | n/a |
| Matched against | full `url.spec()` incl. fragment | full spec minus fragment | n/a |
| Case sensitivity | sensitive | sensitive | n/a |
| Empty glob list | no restriction | `userScripts` API: no restriction (normalized to null). Manifest `content_scripts`: matches nothing (not normalized) | n/a |
| Empty-string glob | matches nothing | matches nothing | n/a |
| matches/include_globs relation (static content scripts) | AND | AND | globs ignored; effectively no relation |
| matches/include_globs relation (dynamic user scripts) | OR | OR | n/a |
| exclude_globs applied | yes | yes | no (FIXME, never consulted) |

## Resolution of the manifest `content_scripts` empty-glob-list question
Traced end to end from the schema through the WebIDL dictionary default to the C++ match check (see section 5, Gecko): the `content_scripts` manifest path does not carry the `nonEmptyOrNull` normalization the `userScripts` runtime API applies, so `"include_globs": []` in a manifest is a real divergence from Chromium, and from Gecko's own `userScripts` API, not an open question.

## 7. Whether a parse algorithm is warranted

A match pattern has a grammar with real failure modes (no `://`, no `path`, a bad `host` shape) that a `parse a match pattern` algorithm and an "unparseable" statement can meaningfully describe. A glob has no such grammar: the two engines that implement matching accept any string as a glob. Chromium's `ParseGlobs` (`extensions/common/utils/content_script_utils.cc:389-401`) appends every string in the manifest array without validating its shape. Gecko's `MatchGlobCore` constructor (`MatchPattern.cpp:747-801`) always compiles successfully -- it branches on whether the string contains a wildcard character, never on whether the string is well-formed, because there is no ill-formed shape to check for. Neither engine has a rejection path for a glob string, unlike the version-string and match-pattern grammars. Conclusion: no `parse a glob` algorithm and no "unparseable glob" statement are warranted for `sections/globs.bs`; there is nothing for either to describe.

## 8. Note on the section's own definition text

The section's lead paragraph previously stated flatly that `?` "matches one character," immediately followed by an issue asking whether `?` matches exactly one character or zero-or-one. Since the "Verdict" in section 1 above is that this exact claim is the error already published in upstream `index.bs` (see also the README's second correction), stating it as settled fact in this draft's own definition reproduced the error it exists to flag. The definition now describes `*` and `?` as the two wildcard characters without asserting `?`'s match count, leaving that entirely to the issue that already states both engines' positions.

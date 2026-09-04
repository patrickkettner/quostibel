# Match patterns: three-engine source findings

All citations are file:line against the Chromium, Gecko and WebKit source trees,
read only, not built.

## 1. Source files that actually implement match patterns

- Chromium: `extensions/common/url_pattern.h`, `extensions/common/url_pattern.cc`,
  `extensions/common/url_pattern_set.cc`. Grammar tests:
  `extensions/common/url_pattern_unittest.cc`.
- Gecko: `toolkit/components/extensions/MatchPattern.h`,
  `toolkit/components/extensions/MatchPattern.cpp`. JSON-schema-level grammar:
  `toolkit/components/extensions/schemas/manifest.json` (`MatchPattern`,
  `MatchPatternRestricted`, `MatchPatternUnestricted` defs, lines 746-780).
  Behavioral tests: `toolkit/components/extensions/test/xpcshell/test_MatchPattern.js`.
- WebKit: the actual grammar/parsing/matching engine is
  `Source/WebCore/page/UserContentURLPattern.h` / `.cpp` (NOT
  `Shared/Extensions/WebExtensionMatchPattern.mm`, which does not exist in this
  tree). The extensions-specific wrapper is
  `Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.h` / `.cpp`
  (path is `UIProcess/Extensions/`, not `Shared/Extensions/`). Tests:
  `Tools/TestWebKitAPI/Tests/WebKit/WKWebView/WKWebExtensionMatchPattern.mm`.

## 2. Grammar, component by component

### Scheme

- Chromium (`url_pattern.cc:194-234`, `:382-391`): scheme is everything before
  `://` (or bare `:` for non-standard schemes, `url_pattern.cc:207-231`).
  `*` is accepted as a literal scheme token; `SetScheme` narrows
  `valid_schemes_` to `SCHEME_HTTP | SCHEME_HTTPS` when the scheme is `*`
  (`url_pattern.cc:382-391`). The scheme string is compared byte-for-byte
  against a fixed lowercase table (`url_pattern.cc:398-404`), so an uppercase
  scheme token is rejected. Schemes valid at all for a `URLPattern` are
  gated by the caller-supplied `valid_schemes` bitmask
  (`url_pattern.h:52-74`); for `content_scripts.matches` /
  `host_permissions` the mask is `Extension::kValidHostPermissionSchemes`
  (`extensions/common/extension.cc:217-221`) = chrome (WebUI), http, https,
  file, ftp, ws, wss, urn:uuid-in-package. For content-script injection
  specifically Chromium uses a narrower mask,
  `UserScript::kValidUserScriptSchemes` (`extensions/common/user_script.cc:67-73`)
  = chrome, http, https, file, ftp, uuid-in-package -- no ws/wss, unlike
  `host_permissions`. `chrome-extension:` (the extension's own scheme) is not
  in either mask.

- Gecko (`MatchPattern.cpp:265-283`): scheme is everything before the first
  `:`. `*` maps to `WildcardSchemes()` = `{http, https, ws, wss}`
  (`MatchPattern.cpp:94-95`) -- 4 schemes, not 2. A literal scheme is
  accepted only if `!aRestrictSchemes` or the scheme is in
  `PermittedSchemes()` = `{http, https, ws, wss, file, ftp, data}`
  (`MatchPattern.cpp:83-85`) or is `moz-extension`
  (`MatchPattern.cpp:275-276`). `aRestrictSchemes` is `true` for ordinary
  (unprivileged) extensions; `about:` and `resource:` are gated separately by
  the manifest JSON schema (`schemas/manifest.json:775-784`,
  `MatchPatternUnestricted`) and are rejected by `MatchPatternCore` for a
  restricted pattern.

- WebKit (`UserContentURLPattern.cpp:145-153`; scheme validity gate in
  `WebExtensionMatchPattern.cpp:56-60`): `validSchemes()` = `{"*", http, https,
  file, ftp, webkit-extension}` plus any scheme registered by
  `registerCustomURLScheme` (`WebExtensionMatchPattern.cpp:94-105`, this is
  how Safari's actual `safari-web-extension` scheme gets in). No ws/wss, no
  data, no chrome/resource/about analogue are ever valid scheme tokens for a
  WebKit match pattern. `*` maps to `url.protocolIsInHTTPFamily()` when
  matching a URL (`UserContentURLPattern.cpp:204-212`,
  `WTF/wtf/URL.cpp:964-972`, prefix check for `http`/`https` only -- 2
  schemes, same width as Chromium's `*` but different from Gecko's 4).

### Host

- Leading `*.` means "match subdomains", stored with the `*.` stripped; a
  bare `*` alone means "match all hosts" (host stored empty,
  match-subdomains true). All three engines agree on this:
  - Chromium: `url_pattern.cc:306-316`.
  - Gecko: `MatchPattern.cpp:318-322`.
  - WebKit: `UserContentURLPattern.cpp:131-138`.
- A `*` anywhere else in the host is a parse error in all three:
  - Chromium: `url_pattern.cc:328-330` (`kInvalidHostWildcard`); test cases
    `url_pattern_unittest.cc:43-47` (`http://*foo/bar`,
    `http://foo.*.bar/baz`, `http://foo.*/bar`).
  - Gecko: schema regex forbids it structurally
    (`schemas/manifest.json:765`: `^(https?|wss?|file|ftp|\*)://(\*|\*\.[^*/]+|[^*/]+)/.*$`).
  - WebKit: `UserContentURLPattern.cpp:55-58`/`170-171`
    (`Error::InvalidHost`); test cases
    `WKWebExtensionMatchPattern.mm:108-115` (`http://*foo/bar`,
    `http://foo.*.bar/baz`).
- Ports: only Chromium supports a port component as real grammar.
  - Chromium: explicit `<host>:<port>` parsing
    (`url_pattern.cc:266-300`), `port_` defaults to `"*"` (any port) and is
    checked at match time via `MatchesPortPattern` inside
    `MatchesSecurityOriginHelper` (`url_pattern.cc:893-908`, called from
    `MatchesURL` at `url_pattern.cc:467-468`). A pattern that names an
    explicit port only matches that port:
    `url_pattern_unittest.cc:705-713` (`IgnorePorts` test -- misleadingly
    named; it actually proves port IS enforced: pattern with `:8080`
    does NOT match a URL on `:1234`).
  - Gecko: no port grammar at all. `MatchPatternCore`'s host-parsing
    loop (`MatchPattern.cpp:285-331`) never looks for a `:` port separator;
    any `:port` text becomes part of the literal domain string, which then
    can never equal a real (portless) `nsIURI::GetHost()` value. Proven
    empirically: pattern `http://mozilla.org:8080/` does NOT match URL
    `http://mozilla.org:8080` (`test_MatchPattern.js:120`), while pattern
    `http://mozilla.org/` (no port) DOES match a URL on port 8080
    (`test_MatchPattern.js:118`). Ports are simply never compared; a pattern
    with a port silently becomes unmatchable rather than erroring.
  - WebKit: ports are explicitly rejected as a parse error.
    `UserContentURLPattern.cpp:66-81` (and the same block duplicated at
    `:178-186` for the string-parse path) detects a bare `:` (or a `:` after
    an IPv6 `]`) in the host and returns `Error::InvalidHost`. Confirmed by
    tests: `WKWebExtensionMatchPattern.mm:72-73`
    (`http://www.example.com:8080/` -> "host ... is invalid"),
    `:144-145`, `:150-151` (IPv6 with port also rejected). A URL's own port
    is ignored when matching (pattern has none to compare):
    `WKWebExtensionMatchPattern.mm:367-369`, `:372-374`
    (`http://127.0.0.1/*` matches both port-less and `:8080` URLs).
- IPv6 literals: bracket syntax `[...]` accepted by all three engines,
  but stored differently.
  - Chromium keeps the brackets in `host_` (`url_pattern_unittest.cc:106-134`,
    expected_host is `"[2607:f8b0:4005:805::200e]"` with brackets).
  - Gecko strips the brackets (`MatchPattern.cpp:323-327`,
    `CopyUTF16toUTF8(Substring(host, 1, host.Length() - 2), mDomain)`).
  - WebKit's own parse code operates on the bracketed text directly for the
    "no port" check (`UserContentURLPattern.cpp:67-77`) but the stored
    `m_host` still contains the brackets (no bracket-stripping call is
    present); matched literally case-insensitively against the URL's
    bracketed host string (`UserContentURLPattern.cpp:224-247`). Test:
    `WKWebExtensionMatchPattern.mm:372-374` uses `http://[::1]/*` throughout.
- IDN / punycode: only Chromium normalizes the pattern's host to
  punycode at parse time.
  - Chromium: `url_pattern.cc:332-341` calls `net::CanonicalizeHost()`.
    Test: `url_pattern_unittest.cc:1072-1108` (`UncanonicalizedUrl`),
    pattern host `ɡoogle.com` is canonicalized to `xn--oogle-qmc.com` at
    parse time, and the pattern then matches both the Unicode and punycode
    forms of the URL.
  - Gecko: no IDNA/ACE call anywhere in `MatchPattern.cpp` (grepped for
    `LowerCase`, `ToLower`, `idna`, `ace`, `punycode`, `normali`: no hits).
    The pattern's host is a raw UTF-8 copy of the manifest text
    (`MatchPattern.cpp:321,327,329`) and is compared byte-for-byte against
    `nsIURI::GetHost()`, which for a real navigated URL is already
    ASCII/punycode. A Unicode host written directly in a match pattern will
    not match the real (punycode) host unless the extension author writes
    the punycode form themselves. Not exercised by any test found in
    `test_MatchPattern.js`; this is inferred directly from the absence of a
    normalization call, not from a passing/failing test.
  - WebKit: same absence -- no IDNA/ACE call in `UserContentURLPattern.cpp`.
    Host is compared case-insensitively but with no punycode conversion.
- Case sensitivity of the host: Chromium's `MatchesHost` is a plain
  string `==`/`EndsWith` (`url_pattern.cc:514-546`) that works because both
  sides are already canonicalized to lowercase (pattern host by
  `net::CanonicalizeHost` at parse; URL host by GURL parsing). Gecko's
  `MatchesDomain` is a plain byte comparison
  (`MatchPattern.cpp:372-386`) with no lowering on either side for the
  pattern's stored `mDomain`, only relying on `nsIURI` already normalizing
  real URLs to lowercase; an intentionally-uppercase pattern host is
  therefore compared against a lowercase real host and will not match
  (inferred from source; not directly tested). WebKit's `matchesHost`
  explicitly calls `equalIgnoringASCIICase` /
  `endsWithIgnoringASCIICase` (`UserContentURLPattern.cpp:224-247`) --
  genuinely, deliberately case-insensitive regardless of how the pattern
  text was written.
- Trailing dots: Chromium explicitly strips trailing dots from both the
  pattern host and the tested host before comparing
  (`url_pattern.cc:129-132`, `CanonicalizeHostForMatching`), verified by
  `url_pattern_unittest.cc:967-1005` (`TrailingDotDomain`, both
  `example.com` and `example.com.` patterns match both
  `http://example.com/` and `http://example.com./`). Gecko and WebKit
  both do not strip a trailing dot on either side, traced past
  `MatchPattern.cpp`/`UserContentURLPattern.cpp` into the URL-host layer
  each engine's earlier pass left unexamined: Gecko's pattern host is a
  raw `CopyUTF16toUTF8` of the manifest text with no dot handling
  (`MatchPattern.cpp:321-329`), and its URL host goes through
  `NS_DomainToDisplayAndASCII` (`nsStandardURL.cpp:437-452`), which for a
  real navigated host defers to the UTS46 domain-to-ASCII algorithm
  (`netwerk/base/idna_glue/src/lib.rs`, backed by the `idna` crate); that
  algorithm treats a trailing "root label" dot as valid and preserves it
  rather than removing it (`third_party/rust/idna/src/uts46.rs:458-477`,
  `verify_dns_length`'s `allow_trailing_dot` parameter strips it only for
  a length check, not from the returned domain). WebKit's pattern host is
  likewise a raw substring with no dot handling (`m_host =
  pattern.substring(...)`, `UserContentURLPattern.cpp:164`), and its URL
  host comes from `URLParser::domainToASCII`
  (`Source/WTF/wtf/URLParser.cpp:2566-2605`), whose plain-ASCII fast path
  only lowercases the string unchanged and whose ICU/UTS46 path
  (`uidna_nameToASCII`) is the same standard algorithm that preserves a
  trailing dot. Resolved: neither Gecko nor WebKit strip trailing dots on
  either side, so (unlike Chromium) `example.com` and `example.com.` are
  two different hosts to both engines.
- IPv4/IP literals: no engine treats an IP literal specially in the
  host grammar; it is stored and compared as an opaque host label like any
  other. Chromium explicitly forbids subdomain-matching against an IP host
  even if the pattern used `*.` (`url_pattern.cc:531-535`,
  `MatchesHost`, `test.HostIsIPAddress()` check). Gecko's `MatchesDomain`
  (`MatchPattern.cpp:372-386`) and WebKit's `matchesHost`
  (`UserContentURLPattern.cpp:224-247`) contain no IP-address detection
  of any kind -- a repository-wide grep of both files for any
  IP-address-related identifier returns nothing in either. Resolved: both
  engines apply their ordinary suffix-matching rule uniformly to an
  IP-literal host exactly as they would to any other host string, with no
  restriction analogous to Chromium's.

### Path

- Required, must start with `/`, in all three engines:
  - Chromium: `kEmptyPath` (`url_pattern.cc:262-264`; test
    `url_pattern_unittest.cc:41` `http://bar` -> `kEmptyPath`).
  - Gecko: schema regex requires `/.*$` after host
    (`schemas/manifest.json:765`); `MatchPatternCore` throws if path is
    empty (`MatchPattern.cpp:342-346`); test
    `test_MatchPattern.js:98` (`http://mozilla.org` with no path is
    invalid).
  - WebKit: `Error::MissingPath` if the text after host doesn't start with
    `/` (`UserContentURLPattern.cpp:84-87`, `:160-162`); test
    `WKWebExtensionMatchPattern.mm:66-67`.
- Wildcard is `*` only (matches zero or more chars), not `?`, in the path
  grammar of a match pattern in all three engines. (`?` as a wildcard is a
  property of the separate `glob` concept used by `include_globs` /
  `exclude_globs`, which the target document already defines distinctly.)
  - Chromium: `base::MatchPattern` glob semantics, single wildcard char `*`
    (`url_pattern.cc:611-684`, only `*` is special-cased anywhere in the
    matching code).
  - Gecko: `MatchGlobCore` constructed with `aAllowQuestion = false` for a
    match pattern's path (`MatchPattern.cpp:352`), vs. `true` for the
    separate `MatchGlob` JS-exposed class used by `include_globs`
    (`MatchPattern.cpp:826-832`). Confirmed by test: `?` used as a literal
    wildcard only in the `MatchGlob`-specific tests
    (`test_MatchPattern.js:463-476`, `http://???.example.com/foo/*`), never
    in the `MatchPatternCore` (`add_task test_MatchPattern_matches`) tests.
  - WebKit: `MatchTester` in `UserContentURLPattern.cpp:249-321` only
    special-cases `*`; every other character including `?` is compared
    literally. Confirmed: `?` appears as a literal path character in match
    pattern tests, e.g. `WKWebExtensionMatchPattern.mm:295-296,398-400`
    (`*://*/foo?bar*`), never as a wildcard.
- Query string: included in what gets matched against the path pattern
  in Chromium and Gecko, but appears to be excluded in WebKit.
  - Chromium: `MatchesURL` uses `GURL::PathForRequest()`
    (`url_pattern.cc:462`), documented as "the path, parameter, and query
    portions of the URL" (`url/gurl.h:380-382`) -- i.e. path + query,
    fragment excluded.
  - Gecko: `URLInfo::Path()` uses `nsIURI::GetPathQueryRef` on the
    ref-stripped URI (`MatchPattern.cpp:152-159`, `URINoRef()` at
    `:175-182`) -- path + query, fragment excluded. Fragment-exclusion
    directly tested: `test_MatchPattern.js:172-175` (pattern
    `http://mozilla.org/base` matches URL
    `http://mozilla.org/base#some-fragment`).
  - WebKit: `matchesPath(const URL& url)` calls `matchesPath(url.path()...)`
    (`UserContentURLPattern.h:77`) using only `WTF::URL::path()`
    (`WTF/wtf/URL.h:155`), a distinct accessor from `query()`
    (`WTF/wtf/URL.h:157`). No call to `query()` appears anywhere in
    `UserContentURLPattern.cpp`. This means a WebKit match pattern's path
    component is compared against the URL's path only, not path+query.
    Not confirmed by a passing/failing test with a literal `?` query
    separator in this file (the closest tests,
    `WKWebExtensionMatchPattern.mm:398-400`, use a percent-encoded `%3F`
    that is part of the path itself, not an actual query separator); this
    conclusion is drawn from the source (which accessor is called), not
    from an executed test, and is flagged as such in the draft.
- Percent-encoding: Chromium unescapes both the tested path and the
  pattern's raw path before comparing, trying both the unescaped-UTF8 and
  raw forms (`url_pattern.cc:590-684`, tests
  `url_pattern_unittest.cc:160-205`, `1398-1533`). WebKit does the
  opposite: no decoding at all, comparison is on the literal (possibly
  percent-encoded) string as returned by `URL::path()`. Proven directly:
  `WKWebExtensionMatchPattern.mm:398-400` -- pattern with an escaped
  `%3F` in the path only matches a URL with the identical literal `%3F`,
  and a pattern with a literal (unescaped) `?` does not match a URL whose
  path contains `%3F`. Gecko also does no decoding on either side, traced
  past `MatchPattern.cpp` into both the pattern-parsing and URL-accessor
  code that earlier passes flagged as out of scope: the pattern's path is
  a bare `NS_ConvertUTF16toUTF8` of the manifest text with no unescape
  call (`MatchPatternCore::MatchPatternCore`, `MatchPattern.cpp:340`, the
  `NS_ConvertUTF16toUTF8 path(tail);` line feeding `mPath = new
  MatchGlobCore(path, ...)`), and the URL side's `nsIURI::GetPathQueryRef`
  resolves for a standard URL to `nsStandardURL::GetPathQueryRef`
  (`netwerk/base/nsStandardURL.cpp:1367-1370`), which returns
  `Path()` -- a raw substring of the already-built spec buffer
  (`nsStandardURL::Path()`, `netwerk/base/nsStandardURL.h:307`) -- with no
  unescape call anywhere in that path either; its own doc comment reads
  "result may contain unescaped UTF-8 characters", not "result is
  percent-decoded". `MatchGlobCore::Matches` then compares these two
  never-decoded strings directly (`MatchPattern.cpp:809-816`). No test in
  `test_MatchPattern.js` exercises a percent-encoded literal either way.
  Resolved: Gecko performs no percent-decoding on either side, the same
  as WebKit, not the same as Chromium.

## 3. Case sensitivity, overall

- Chromium: the class-level comment nowhere claims case-insensitivity; the
  public `MatchesURL`/`MatchesPath` API takes an explicit
  `case_sensitive` bool that defaults to `true`
  (`url_pattern.h:161-165,180-183`; `url_pattern.cc:426-430,586-590`). Every
  production call site in `extensions/` and `chrome/browser/extensions/`
  that calls `URLPatternSet::MatchesURL` or `URLPattern::MatchesURL` uses
  the single-argument overload, i.e. the `true` (case-sensitive) default --
  confirmed by grep across `extensions/browser`, `extensions/renderer`,
  `extensions/common`, `chrome/browser/extensions` (no call site found
  passing `case_sensitive=false` outside of `url_pattern.cc`/
  `url_pattern_set.cc` themselves and their unit tests). So path matching
  in shipping Chromium is case-sensitive, not case-insensitive, despite
  a `case_sensitive=false` mode existing in the API for callers who want
  it (`CaseInsensitiveMatch` test, `url_pattern_unittest.cc:1358-1397`).
  Host is effectively case-insensitive only because both sides are
  canonicalized to lowercase before the byte comparison, not because of an
  explicit fold. Scheme comparison is a byte-exact match against a
  lowercase table (`url_pattern.cc:398-404`), so an uppercase scheme in
  the pattern text fails to parse as a valid scheme, but a URL's scheme
  is always already lowercased by GURL, so this rarely surfaces as a
  practical divergence.
- Gecko: no case-folding call of any kind (`ToLowerCase`,
  `EqualsIgnoreCase`, or otherwise) appears anywhere in
  `MatchPattern.cpp`; path glob matching in `MatchGlobCore::Matches`
  (`MatchPattern.cpp:809-819`) and domain comparison in `MatchesDomain`
  (`MatchPattern.cpp:372-386`) are both plain byte/string comparisons
  with no fold call in either. Host comparison is therefore
  case-sensitive by the same standard already used elsewhere in this
  document for an absence-based finding: the pattern's host is a raw,
  unprocessed copy of the manifest text (see above), and nothing folds
  either side before `MatchesDomain`'s `==`/suffix check runs, so an
  uppercase pattern host will not match a real (lowercase) URL host.
  Confirmed case-sensitive path/glob matching directly by test:
  `test_MatchPattern.js:495-496` (`fail({url: "http://mozilla.org",
  pattern: ["*.ORG/"]})`) -- this specific test is on the `MatchGlob`
  class (used for `include_globs`), not `MatchPatternCore` directly, but
  both share the same `MatchGlobCore` matching primitive
  (`MatchPattern.cpp:809-819`), and no separate lowering exists for
  `MatchPatternCore`'s path use of that primitive
  (`MatchPattern.cpp:413`).
- WebKit: host matching is deliberately, explicitly case-insensitive
  (`equalIgnoringASCIICase`/`endsWithIgnoringASCIICase`,
  `UserContentURLPattern.cpp:228,240`). Path matching
  (`MatchTester`, `UserContentURLPattern.cpp:249-321`) does a plain `==`
  character comparison with no case-folding call, i.e. case-sensitive.
  Scheme matching uses `equalIgnoringASCIICase`
  (`UserContentURLPattern.cpp:211,221`) -- also case-insensitive.

So: all three engines agree the path component is compared
case-sensitively in normal production use. The current target-document
text ("They are case-insensitive.") is not accurate for any of the three
engines' path matching, and is only accurate for WebKit's host/scheme
matching, partially accurate for Chromium's (host/scheme incidentally
case-insensitive via canonicalization, not by design), and not clearly
accurate for Gecko's host matching (no fold found).

## 4. `<all_urls>`

- Chromium: `<all_urls>` doesn't have one fixed scheme set; it matches
  whatever schemes are in the `URLPattern`'s `valid_schemes_` bitmask,
  which is supplied by the caller (`url_pattern.cc:200-204,365-375`;
  `MatchesURL` checks `MatchesScheme` -- which itself gates on
  `IsValidScheme(valid_schemes_)` -- before falling through to the
  `match_all_urls_` shortcut, `url_pattern.cc:446-454`). For the two
  contexts the target document's existing text talks about:
  - `content_scripts.matches` (via `UserScript::ValidUserScriptSchemes`,
    `user_script.cc:108-118`, when not "execute script everywhere"):
    chrome (WebUI, only if `--extensions-on-chrome-urls`), http, https,
    file, ftp, uuid-in-package. No ws/wss, no data, no chrome-extension.
  - `host_permissions` (`Extension::kValidHostPermissionSchemes`,
    `extension.cc:217-221`): chrome (WebUI), http, https, file, ftp, ws,
    wss, uuid-in-package. No data, no chrome-extension.
- Gecko: `<all_urls>` is one fixed set,
  `PermittedSchemes()` = `{http, https, ws, wss, file, ftp, data}`
  (`MatchPattern.cpp:83-85,252-256`). Includes `data:`, which Chromium
  never includes for either `matches` or `host_permissions`. Does not
  include the extension's own scheme (`moz-extension`).
- WebKit: `<all_urls>` is the narrowest of the three by far.
  `matchesURL` for `m_matchesAllURLs`
  (`WebExtensionMatchPattern.cpp:375-379`): if the URL is `file:`, only
  matches when the caller opts in with `Options::AllowFileScheme`
  (default off); otherwise matches only if the URL's scheme is in
  `supportedSchemes()` = `{"*", http, https, webkit-extension}` plus any
  registered custom extension scheme (`WebExtensionMatchPattern.cpp:62-66`,
  `registerCustomURLScheme` at `:94-105` -- this is how the real
  `safari-web-extension` scheme is added at runtime). No ftp, no ws/wss,
  no data, ever. Directly tested:
  `WKWebExtensionMatchPattern.mm:391-395` (`<all_urls>` matches
  `http://example.com/...`, does NOT match `file:///...` without the
  option, does NOT match arbitrary custom schemes like
  `favorites://`/`bookmarks://`/`history://`), and
  `WKWebExtensionMatchPattern.mm:247-251` (pattern-vs-pattern form, same
  file-scheme exclusion).

This is the single largest three-way divergence: Chromium's `<all_urls>`
width depends on which permission surface you ask (6-8 schemes depending
on context, no `data:`), Gecko's is one fixed 7-scheme set that includes
`data:`, WebKit's is a fixed ~3-scheme set (http, https, own extension
scheme) that is dramatically narrower than either and by default excludes
`file:` entirely.

## 5. Matching algorithm / component order

- Chromium `MatchesURL` (`url_pattern.cc:430-469`): scheme first (an
  invalid/mismatched scheme short-circuits before the `match_all_urls_`
  check, so `<all_urls>` still respects the pattern's `valid_schemes_`
  gate) -> `match_all_urls_` shortcut -> require URL has a non-empty path
  -> host+port (`MatchesSecurityOriginHelper`, host then port) -> path.
  `filesystem:` URLs are special-cased: the pattern is matched against the
  filesystem URL's inner URL, with the outer URL's path prefixed onto
  the inner path (`url_pattern.cc:436-465`).
- Gecko `MatchPatternCore::Matches` (`MatchPattern.cpp:400-418`): if
  `aExplicit` (host-permission-style "explicit" match, as opposed to a
  content-script "broad" match) and the pattern matches subdomains,
  immediately fail (`:401-403`) -- i.e. Gecko has a distinct stricter mode
  that rejects any subdomain-wildcard pattern outright, with no equivalent
  concept found in Chromium or WebKit's matching entry points. Then:
  scheme -> domain -> path (only if a path glob is present and not a pure
  wildcard).
- WebKit `WebExtensionMatchPattern::matchesURL`
  (`WebExtensionMatchPattern.cpp:368-391`): validity checks first, then
  the `<all_urls>` shortcut (which has its own scheme-only logic, see
  above section 4), else scheme (unless `IgnoreSchemes` option) -> host ->
  path (unless `IgnorePaths` option).
- All three, therefore, agree on scheme, then host, then path as the
  component order (Chromium interleaves port into the host/origin step).
  Gecko's `aExplicit` early rejection of subdomain patterns is a genuine
  behavior with no counterpart found in the other two engines' match
  entry points, and none was found in their permission-checking code
  either, once traced past the match-pattern classes themselves.
  Chromium's `PermissionSet` distinguishes `explicit_hosts()` from
  `scriptable_hosts()` (`extensions/common/permissions/permission_set.h:36,120,128,159`),
  but that split is about which manifest key declared a pattern
  (`host_permissions`/`permissions` versus `content_scripts.matches`),
  not about whether the pattern contains a subdomain wildcard -- a
  `*.example.com`-style pattern is a perfectly ordinary member of
  `explicit_hosts()`. WebKit's `permissionState()` five-state machine
  (`WebExtensionContext.cpp:866-991`, described further in
  `host-permissions.md`) does split matches into an "Explicitly" and an
  "Implicitly" bucket, but the split there is `matchesAllHosts()` (a
  pattern that matches literally every host, like `<all_urls>` or
  `*://*/*`) versus a pattern that names a specific domain
  (`WebExtensionContext.cpp:924-955`) -- a pattern such as
  `*://*.example.com/*` still lands in the "Explicitly" bucket there,
  because it doesn't match *all* hosts, even though it does carry a
  subdomain wildcard. That is a coarser, different distinction from
  Gecko's rule, which rejects any subdomain-wildcard host (bare `*.`
  prefix), not just a bare `*`/`<all_urls>`-style pattern. Resolved: no
  true equivalent of Gecko's `aExplicit` subdomain rejection exists in
  either Chromium's or WebKit's permission code; the superficial
  Explicitly/Implicitly naming overlap with WebKit is a false lead. As an
  aside, Gecko's own `explicit` flag (exposed to JS as
  `MatchPatternSet.prototype.matches`'s second argument, documented in
  `dom/chrome-webidl/MatchPattern.webidl:40-47,98-105` as "only explicit
  domain matches, without wildcards, are considered") was not found
  passed as `true` by any production caller in
  `toolkit/components/extensions/` or `browser/components/extensions/`
  in this tree -- every call site found (including
  `ExtensionDNR.sys.mjs:1482,1491` and the C++ call sites in
  `WebExtensionPolicy.cpp`/`ChannelWrapper.cpp`) uses the default
  `false`; only test files exercise `true` directly on the class.

## 6. Matching against non-tuple-origin documents

The target document already has a "determine the URL for matching a
document" algorithm (`index.bs`, `## Determine the URL for matching a
document`) that resolves `about:blank`/`about:srcdoc`/`blob:`/`data:`/
`filesystem:` documents (and opaque origins generally) down to either a
concrete `http`/`https`/`file` URL, a serialized tuple origin, or `null`,
before match-pattern matching ever runs. Gecko has source-level support
for exactly this precursor-origin resolution
(`URLInfo::InheritsPrincipal`, `MatchPattern.cpp:184-196`;
`URLInfo::IsNonOpaqueURL` plus `NonOpaqueSchemes` =
`{http, https, file, view-source}`, `MatchPattern.cpp:97-110,198-205`;
consumed in `WebExtensionPolicy.cpp:930,1379,1427-1454`). This confirms
the general shape of the existing document's algorithm is implementable,
and that Gecko's own scheme allowlist for "non-opaque, meaningful as a
literal URL" purposes (`http`, `https`, `file`, `view-source`) is close
to but not identical to the target document's algorithm's `http`/`https`/
`file` set (Gecko additionally treats `view-source:` as non-opaque; the
target document's algorithm has no `view-source` case). Chromium and
WebKit each have an equivalent named concept too, just outside the three
match-pattern-grammar files this task originally scoped in, and outside
the match-pattern code itself (consistent with the sibling finding above
that Chromium's and WebKit's "explicit" analogues also live in
permission/injection code, not the grammar classes):

- Chromium: `ContentScriptInjectionUrlGetter::Get()`
  (`extensions/common/content_script_injection_url_getter.cc:18-`),
  called from `ScriptContext::GetEffectiveDocumentURLForContext`/
  `GetEffectiveDocumentURLForInjection` (`extensions/renderer/script_context.cc:408-434`).
  For `about:`/`blob:`/`data:`/`filesystem:` documents, it resolves the
  frame's origin (or, for an opaque origin, its precursor origin via
  `url::Origin::GetTupleOrPrecursorTupleIfOpaque()`) to a concrete URL,
  gated by a per-content-script `match_origin_as_fallback` behavior
  (`kNever`/`kMatchForAboutSchemeAndClimbTree`/`kAlways`) -- i.e. Chromium
  can climb through an origin's precursor chain, not just to an immediate
  parent document.
- WebKit: `LocalFrame::injectUserScriptImmediately()`
  (`Source/WebCore/page/LocalFrame.cpp:829-852`) substitutes the literal
  parent document's URL (`parentDocument->url()`) when the current
  document's URL is `about:`/`blob:`/`data:` (for
  `UserContentMatchParentFrame::ForOpaqueOrigins`) or specifically
  `about:blank` (`::ForAboutBlank`), driven by the `match_origin_as_fallback`/
  `match_about_blank` manifest keys parsed in
  `WebExtension.cpp:1447-1458`. This only ever looks at
  `document->parentDocument()` one level up; it does not climb an
  opener/precursor chain the way Chromium's does.

Resolved that both engines have the concept; not resolved (and not
attempted further here, since it is outside match-pattern grammar
proper) whether Chromium's precursor-tuple climbing and WebKit's
single-parent substitution produce identical results in every case --
they are visibly different mechanisms and could plausibly diverge for a
multi-level or opener-based frame hierarchy, but confirming that would
need its own dedicated pass. The match-patterns section itself does not
need to redefine any of this; it only needs to state that matching
operates on the URL/origin produced by the target document's existing
algorithm, and must not contradict it.

## 7. Divergence summary (for the Issue: lines in the draft)

1. `<all_urls>` scheme coverage -- Chromium (context-dependent, 6-8
   schemes, never `data:`), Gecko (fixed 7 schemes, includes `data:`),
   WebKit (fixed ~3 schemes: http/https/own-extension-scheme, `file:`
   opt-in only, never ftp/ws/wss/data).
2. `*` scheme-wildcard expansion -- Chromium and WebKit: http+https
   (2 schemes). Gecko: http+https+ws+wss (4 schemes).
3. Port component -- Chromium: real grammar, optional, enforced
   exactly when present. Gecko: no grammar for it; a port in the pattern
   text silently becomes an always-losing literal domain string (not a
   parse error). WebKit: explicit parse-time rejection (`InvalidHost`
   error) of any port syntax in the pattern.
4. `ws:`/`wss:` and `data:` scheme support -- Chromium supports
   `ws`/`wss` for `host_permissions` (not for `content_scripts.matches`),
   never `data:`. Gecko supports both `ws`/`wss` and `data:`
   unconditionally. WebKit supports neither.
5. Case sensitivity of path matching -- all three are actually
   case-sensitive in production, contradicting the target document's
   current "They are case-insensitive" text.
6. Case sensitivity of host matching -- WebKit is deliberately,
   explicitly case-insensitive. Chromium is case-insensitive only as a
   side effect of canonicalizing both sides to lowercase. Gecko has no
   fold at all: no case-folding call of any kind appears in
   `MatchPattern.cpp`, and the pattern's host is stored as a raw,
   unprocessed copy of the manifest text, so an uppercase pattern host
   will not match a real (lowercase) URL host.
7. IDN/punycode canonicalization of the pattern's host -- only
   Chromium does it at parse time. Gecko and WebKit do not; a
   Unicode-literal host in the pattern will not match a real (punycode)
   URL host unless the author writes punycode themselves.
8. Percent-encoding handling of the path -- Chromium unescapes before
   comparing (both sides). WebKit never unescapes (literal byte
   comparison). Gecko never unescapes either (traced into
   `nsStandardURL::GetPathQueryRef`/`Path()`, which returns a raw spec
   substring, and into `MatchPatternCore`'s own path parsing, which is a
   bare UTF-16-to-UTF-8 conversion): Gecko groups with WebKit here, not
   with Chromium.
9. Query string inclusion in path matching -- confirmed directly for all
   three engines, not inferred:
   - Chromium: `URLPattern::MatchesURL` compares against
     `test.PathForRequest()` (`extensions/common/url_pattern.cc:461-467`),
     and `GURL::PathForRequest`/`PathForRequestPiece`
     (`url/gurl.cc:411-431`) spans from the path start through the end of
     the query component (clipped only at a `#` fragment). Query string
     included.
   - Gecko: `URLInfo::Path()` calls `URINoRef()->GetPathQueryRef(mPath)`
     (`toolkit/components/extensions/MatchPattern.cpp:152-157`), an
     nsIURI method that returns path+query with the ref already stripped
     by `URINoRef()`; `MatchPattern::Matches` matches `mPath` against
     `aURL.Path()` (`MatchPattern.cpp:413`). Query string included.
   - WebKit: `WebExtensionMatchPattern::matchesURL` calls
     `pattern().matchesPath(urlToMatch)`
     (`Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.cpp:387`),
     where `pattern()` is a `UserContentURLPattern`
     (constructed from the same string, `WebExtensionMatchPattern.cpp:198`).
     `UserContentURLPattern::matchesPath(const URL& url)` calls
     `url.path().toStringWithoutCopying()`
     (`Source/WebCore/page/UserContentURLPattern.h:77`). `URL::path()` and
     `URL::query()` are separate accessors in WTF's URL
     (`Source/WTF/wtf/URL.h:155,157`); `URL::path()`'s implementation
     returns the substring ending at `m_pathEnd`, and `URL::query()`
     returns the substring starting at `m_pathEnd + 1`
     (`Source/WTF/wtf/URL.cpp:403-416`) -- mutually exclusive spans by
     construction. So in this source, WebKit's match-pattern path
     matching reads only the path and does **not** include the query
     string. This directly contradicts the "Safari aligned as of STP 192"
     claim from the WebKit engineer's comment on
     [w3c/webextensions#580](https://github.com/w3c/webextensions/issues/580#issuecomment-2070916942):
     either the STP 192 fix is not present in the WebKit tree read for
     this task (checked-out branch `webextension-idl-declarations`, tip
     commit dated 2026-08-15; `git log` on `UserContentURLPattern.cpp`/`.h`
     shows only a single, unrelated tooling commit touching those files,
     which is consistent with a shallow or partial history and does not
     establish the file's real age), or the change described in the
     comment lives in code this task did not examine. Neither is
     established from this tree; the source read here shows exclusion,
     not inclusion, and that is reported as what was found, not as proof
     the STP 192 claim is false.
10. IPv6 bracket storage -- Chromium and WebKit keep the brackets in
    the stored host; Gecko strips them. Not expected to be
    externally observable, noted for completeness only, not drafted as
    a normative Issue.
11. Trailing-dot host normalization -- Chromium explicitly strips
    trailing dots before comparing hosts. Neither Gecko nor WebKit do:
    traced past `MatchPattern.cpp`/`UserContentURLPattern.cpp` into each
    engine's URL-host layer (Gecko's `nsStandardURL`/IDNA-processing
    path, WebKit's `URLParser::domainToASCII`), and both preserve rather
    than strip a trailing dot, matching the standard domain-to-ASCII
    algorithm's own treatment of the trailing "root label" dot as valid
    and significant, not something to normalize away.
12. Gecko's `aExplicit` early-reject of subdomain-wildcard patterns --
    traced into both Chromium's and WebKit's permission-checking layers
    (not just their match-pattern entry points) and no true analogue was
    found in either; the closest-sounding candidates (Chromium's
    `explicit_hosts()`/`scriptable_hosts()` split, WebKit's
    Explicitly/Implicitly `PermissionState` values) turn out to be
    different concepts on inspection (manifest-key provenance for
    Chromium; "matches literally all hosts" vs. "names a specific
    domain" for WebKit, which still treats a subdomain-wildcard pattern
    as "Explicitly"). Noted for awareness, not drafted as a normative
    Issue in the target document, since it is a permission-classification
    behavior layered on top of match-pattern matching, not core grammar.

## 8. Things not determined from the three originally-scoped files, resolved by reading further

Every item below was left open by an earlier pass because the three
files it started from (`MatchPattern.cpp`/`.h`,
`UserContentURLPattern.cpp`/`.h`, `url_pattern.cc`/`.h`) don't contain
the answer. All four were resolved by following the same call chains
into the files that do:

- Gecko's percent-decoding: resolved in section 2 above and item 8 -- no
  decoding on either side, traced into `nsStandardURL.cpp` and
  `MatchPatternCore`'s own path-parsing code.
- Chromium's and WebKit's permission-checking layers for an analogue of
  Gecko's `aExplicit` subdomain rejection: resolved in section 5 above
  and item 12 -- no true equivalent in either, traced into
  `permission_set.h`/`.cc` for Chromium and `WebExtensionContext.cpp`'s
  `permissionState()` for WebKit.
- Trailing-dot stripping in Gecko and WebKit: resolved in the Host
  subsection above and item 11 -- neither strips it, traced into each
  engine's URL/IDNA host-normalization code.
- The IP-literal-vs-subdomain-wildcard restriction in Gecko and WebKit:
  resolved in the Host subsection above -- neither has any IP-address
  detection logic in their match/domain-comparison functions, so neither
  restricts subdomain-wildcard matching against an IP-literal host the
  way Chromium does.

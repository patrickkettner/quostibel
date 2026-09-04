# Host permissions / Cross-origin fetch / activeTab: source findings

All paths are relative to the three read-only source trees (Chromium, Gecko, WebKit).

Every claim below is backed by a file:line citation to source actually read
in this session. Nothing here is recalled from training data about these
codebases; where I could not find a citation I say so explicitly.

## 1. What a granted host permission authorizes, per engine

### Chromium

The single choke point is `PermissionsData::CanRunOnPage()` (checked via
`GetPageAccess()` / `CanAccessPage()` and `GetContentScriptAccess()` /
`CanRunContentScriptOnPage()`), `extensions/common/permissions/permissions_data.cc:650-696`.
It gates, in order: enterprise policy blocklist (`IsPolicyBlockedHostUnsafe`,
`permissions_data.cc:664`), restricted URLs (`IsRestrictedUrl`,
`permissions_data.cc:665`), user-level site blocking
(`IsUrlBlockedByUser`, `permissions_data.cc:670`), then tab-specific
patterns, then `permitted_url_patterns` (the extension's granted host
permissions), then `withheld_url_patterns` (`permissions_data.cc:675-687`).

This same `PageAccess`/`HasHostPermission` check is reused, not
reimplemented, by every API that needs host-permission gating:
- Content script injection: `GetContentScriptAccess` calls `CanRunOnPage`
  with `explicit_hosts()` + `scriptable_hosts()`
  (`permissions_data.cc:450-460`).
- `cookies` API: `CheckHostPermissions()` calls
  `extension->permissions_data()->GetPageAccess(url, ...)`,
  `chrome/browser/extensions/api/cookies/cookies_api.cc:75-91`.
- `webRequest` observation: `WebRequestPermissions::CanExtensionAccessURL`
  wraps `GetPageAccess`,
  `extensions/browser/api/web_request/web_request_permissions.cc:69,411-436`.
- `tabs` URL/title visibility: gated on `tabs` permission OR
  `HasHostPermission(web_contents->GetURL())`,
  `chrome/browser/extensions/api/tabs/tabs_api.cc:2060-2069`.
- Cross-origin `fetch`/XHR from extension pages: the extension's
  *effective* host permissions (`GetEffectiveHostPermissions()`) are turned
  into a `CorsOriginAccessList` entry keyed on `extension.origin()`,
  `extensions/common/cors_util.cc:70-108`, installed via
  `content::CorsOriginPatternSetter::Set(browser_context, extension.origin(), ...)`,
  `extensions/browser/network_permissions_updater.cc:39,101-119`.

So in Chromium, a single host permission grant covers: content script
injection, `cookies`, `webRequest` observation (not blocking without
`webRequestBlocking`/`webRequestAuthProvider`, a separate API permission),
`tabs` URL/title visibility, and CORS-free fetch from extension-page
contexts (see section 2 for content scripts specifically, which do NOT get
this last one since Chrome 87).

### Gecko

The choke point is `WebExtensionPolicyCore::CanAccessURI()`,
`toolkit/components/extensions/WebExtensionPolicy.cpp:325-349`, which
checks restricted URIs, quarantined URIs, file-scheme opt-in, and finally
`mHostPermissions->Matches(aURI, aExplicit)` (`WebExtensionPolicy.cpp:348`).
`BasePrincipal::AddonAllowsLoad()` calls into the same `CanAccessURI` from
`caps/BasePrincipal.cpp:1393-1400`, so principal-level CORS/load checks for
an extension's own principal go through the identical host-permission set.

Per-API reuse:
- `cookies` API: `extension.allowedOrigins.matches(uri)` /
  `matchesCookie(cookie)`,
  `toolkit/components/extensions/parent/ext-cookies.js:190,497,552`.
- `webRequest`: filters built from `extension.allowedOrigins.patterns`,
  `toolkit/components/extensions/parent/ext-webRequest.js:52`.
- `tabs`: `hasTabPermission` is `tabs` permission OR `hasActiveTabPermission`
  OR `matchesHostPermission`,
  `toolkit/components/extensions/parent/ext-tabs-base.js:188-199`.

So Gecko's granted-host-permission set gates the same list as Chromium:
content scripts, cookies, webRequest, tabs visibility, plus (for MV2 only,
see section 2) content-script `fetch`/XHR.

### WebKit

The choke point is `WebExtensionContext::permissionState(const URL&, ...)`,
`Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:866-991`, a
five-state machine (`Unknown`, `Requested{Im,Ex}plicitly`,
`Denied{Im,Ex}plicitly`, `Granted{Im,Ex}plicitly`) that checks, in order:
the extension's own URL (`isURLForThisExtension`, line 871), scheme
validity, file-scheme opt-in, a tab's *temporary* activeTab pattern
(line 880-883), then explicit deny/grant patterns, then wildcard
(`<all_urls>`-style) deny/grant patterns, and only if
`SkipRequestedPermissions` is not set, requested/optional patterns.
`hasPermission()` (`WebExtensionContext.cpp:745-803`) collapses this to a
boolean, treating only the two `Granted*` states as true.

Per-API reuse:
- `cookies`: `hasPermission(url)` at
  `Source/WebKit/UIProcess/Extensions/Cocoa/API/WebExtensionContextAPICookiesCocoa.mm:81,103,174,194`.
- `webRequest`: `hasPermissionToSendWebRequestEvent()` requires
  `hasPermission(WebExtensionPermission::webRequest())` AND
  `hasPermission(resourceURL, tab)`,
  `Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm:1703-1721`.
- `tabs`: `hasPermission(const URL&, tab, options)` defaults to
  `PermissionStateOptions::RequestedWithTabsPermission`,
  `Source/WebKit/UIProcess/Extensions/WebExtensionContext.h:459`, and
  `permissionState()` explicitly OKs `tabs`-permission holders at
  `WebExtensionContext.cpp:987,1080`.
- Content script injection: `addInjectedContent(..., grantedMatchPatterns)`
  only injects into patterns present in the *granted* set,
  `Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:1241-1267`.
- CORS-free `fetch`/XHR: wired into the **extension page** WKWebView
  configuration only (`_corsDisablingPatterns` +
  `_crossOriginAccessControlCheckEnabled = NO`),
  `Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm:2489-2508`,
  sourced from `corsDisablingPatterns()` which walks
  `grantedPermissionMatchPatterns()`,
  `Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:1764-1776`.

Same authorized-capability list as the other two engines: content scripts,
cookies, webRequest, tabs visibility, extension-page CORS-free fetch. The
divergence is not in *what* is gated, it's in *when* the grant exists (see
section 3) and in content-script fetch specifically (section 2).

**Finding for the spec**: across all three engines, one host-permission
grant is the single gate for content script injection, `cookies`,
`webRequest` observation, and `tabs` URL/title visibility. This is
consistent enough to specify as a single [=extension has access to a
URL=] (or similarly named) algorithm, reused everywhere. No three-way
divergence found on this point beyond content-script fetch, which is
covered next.

## 2. Cross-origin fetch: which contexts bypass CORS

This is the real divergence point, and it separates into "extension pages"
(background/popup/options) vs "content scripts."

### Extension pages (background, popup, options): all three engines agree

- Chromium: `docs/website/site/Home/chromium-security/extension-content-script-fetches/index.md:27-29`:
  "Extension pages, such as background pages, popups, or options pages, are
  unaffected by this change and will continue to be allowed to bypass CORS
  for cross-origin requests as they do today." Mechanism:
  `CorsOriginAccessList` keyed on `extension.origin()`
  (`extensions/common/cors_util.cc:70-108`), which every request whose
  initiator resolves to `chrome-extension://<id>` (i.e. an extension page)
  is checked against.
- Gecko: extension pages load with `extensionPrincipal` as their node
  principal directly (not expanded), and `caps/BasePrincipal.cpp:1393-1400`
  routes CORS-relevant principal checks for any extension-affiliated
  principal through `WebExtensionPolicyCore::CanAccessURI`, which consults
  `mHostPermissions` (`WebExtensionPolicy.cpp:348`) unconditionally,
  independent of manifest version.
- WebKit: `webViewConfiguration()` (used to build every extension-page
  WKWebView; see call in `loadBackgroundContent`/popup construction paths)
  sets `_corsDisablingPatterns` and disables cross-origin access control
  outright, `WebExtensionContextCocoa.mm:2503-2504,2508`.

### Content scripts: the divergence, and how it resolved

**Chromium** removed CORS bypass from content scripts starting Chrome 73
(CORB) and completed it in Chrome 85 (CORS), fully removing the
allowlist in Chrome 87
(`docs/website/.../extension-content-script-fetches/index.md:24-33,96-104,138-142`).
Quote: "content scripts will be subject to the same request rules as the
page they are running within" (line 28-29). "The changes means that
cross-origin fetches initiated from content scripts will have an Origin
request header with the page's origin" (line 116-118). This predates MV3
and applies uniformly to MV2 and MV3 extensions today; it is not a
manifest-version switch, it is a platform behavior change that already
shipped for everyone.

**Gecko** ties this directly to manifest version, and the source comments
say so explicitly. The content-script sandbox is created with an
`ExpandedPrincipal`-style principal list `[contentPrincipal,
extensionPrincipal]`,
`toolkit/components/extensions/ExtensionContent.sys.mjs:1047`. Then:
```
let isMV2 = extension.manifestVersion == 2;
...
if (isMV2) {
  // In MV2, fetch/XHR support cross-origin requests.
  // WebSocket was also included to avoid CSP effects (bug 1676024).
  wantGlobalProperties.push("XMLHttpRequest", "fetch", "WebSocket");
} else {
  // In MV3, fetch/XHR have the same capabilities as the web page.
  ...
}
```
`ExtensionContent.sys.mjs:1063-1074`. In MV2, the sandbox's own
`fetch`/`XMLHttpRequest`/`WebSocket` are added as sandbox globals bound to
the combined (page + extension) principal, so they inherit the extension's
host permissions and bypass the page's CORS restrictions. In MV3, those
globals are *not* pushed (only `window.JSON` is patched,
`ExtensionContent.sys.mjs:1116-1119`), so `fetch`/XHR inside an MV3 content
script resolve to the page's own `window.fetch`/`XMLHttpRequest`, which run
under the page's own principal for CORS purposes -- matching Chromium's
already-shipped model.

**WebKit** ties the CORS-disabling `WKWebViewConfiguration` exclusively to
extension pages (`webViewConfiguration()`,
`WebExtensionContextCocoa.mm:2497-2508`); content scripts execute inside
the ordinary tab `WKWebView` (a different content world,
`m_contentScriptWorld`, selected in `toContentWorld()`,
`WebExtensionContext.cpp:1281-1298`), which never receives
`_corsDisablingPatterns`. Corroborating evidence:
`resourceLoadDidCompleteWithError()` reprompts for permission on a CORS
failure only when "the URL of the frame where the request originated
corresponds to this extension"
(`WebExtensionContextCocoa.mm:1802-1812`, quoting the comment at
1802-1804), i.e. this repair path is for extension-page fetches, not
content-script fetches.

Resolved, not merely absence-based: `webViewConfiguration()`
(`WebExtensionContextCocoa.mm:2500-2506`) sets `isManifestVersion3` from
`extension->supportsManifestVersion(3)` and uses it to pick the CSP mode
(`_contentSecurityPolicyModeForExtension`) two lines above where it sets
`_corsDisablingPatterns`/`_crossOriginAccessControlCheckEnabled = NO` --
the CORS-bypass properties are set unconditionally, with no
`isManifestVersion3` branch, in the same function that already branches on
manifest version for a neighboring property. An MV2-only carve-out for
content-script CORS, if one existed, would show up as exactly this kind of
branch and does not. Content scripts are added via `API::UserScript` into
the `ContentScript` content world (`WebExtensionContext.cpp:1398`,
`addInjectedContent`), which is injected into the tab's own `WKWebView`,
never the extension-page `WKWebViewConfiguration` that carries the bypass.
No MV2/MV3 branch on CORS behavior exists anywhere in
`Source/WebKit/UIProcess/Extensions/` or
`Source/WebKit/WebProcess/Extensions/` (grepped broadly for
`corsDisablingPatterns`/`CORS`/`cross-origin`). The checked-out tree's git
history is too shallow to read (3 commits total, branch
`webextension-idl-declarations`, no history on the relevant files), so nothing
here is drawn from git log. Cross-checked against public Safari Web
Extension developer discussion (Apple Developer Forums threads on Safari
Web Extension CORS errors): every such report describes content scripts as
subject to the same cross-origin restrictions as the host page, with no
report or documentation of a historical bypass for either manifest
version; the reported CORS gaps are all in background/service-worker
contexts, matching this source tree's finding that the bypass is
extension-page-only. **Conclusion: WebKit has never given content scripts
a cross-origin fetch bypass, for either manifest version** -- Safari's
content-script fetch behavior has always matched Chrome's and Firefox's
current (post-MV3) state, not Firefox's legacy MV2 exemption.

**Finding for the spec**: extension pages bypass CORS via host permissions
in all three engines, uniformly, regardless of manifest version. Content
scripts do NOT get this bypass in MV3, in any of the three engines (all
three now agree: content-script fetch/XHR runs with the page's own origin
and CORS rules). Content scripts DID get the bypass under MV2 in Chromium
(pre-Chrome-87) and Gecko (comment-confirmed, still the shipping MV2
behavior in this Gecko tree); WebKit never offered it, for either manifest
version (see above).

## 3. Install-time grant vs. runtime grant; optional host permissions

### Chromium

Required `permissions`/`host_permissions` are parsed by
`PermissionsParser::ParseHelper` / `ParseHostPermissions`,
`extensions/common/manifest_handlers/permissions_parser.cc:206-296`. In
MV3 (`manifest_version() >= 3`), host-permission-looking strings inside
`permissions` produce an install warning instead of being treated as
hosts -- `host_permissions` is the only valid key for them,
`permissions_parser.cc:277-286` (data flows into
`initial_required_permissions_->host_permissions` only from the dedicated
`host_permissions` key at `permissions_parser.cc:429-442`).

Chromium additionally supports **runtime withholding** of granted host
permissions ("click to script" / runtime host permissions), independent of
whether they came from a required or optional key:
`ScriptingPermissionsModifier::SetWithholdHostPermissions/GrantHostPermission/RemoveGrantedHostPermission`,
`extensions/browser/permissions/scripting_permissions_modifier.h:46-73`.
This is gated by `PermissionsManager::CanAffectExtension()`, which requires
`util::CanWithholdPermissionsFromExtension()` -- false for component
extensions, policy-installed extensions, and extensions on the
script-everywhere allowlist,
`extensions/browser/extension_util.cc:320-335`. So: **required
host_permissions are auto-granted at install** but Chrome may subsequently
let the user withhold them on a per-site basis, at which point the
extension effectively sees a runtime-request flow. Optional
(`optional_host_permissions`) permissions are never auto-granted; they are
requested with `permissions.request()` -- parsed the same way but stored in
`initial_optional_permissions_`, `permissions_parser.cc:414-422,444-448`.

### Gecko

Required host permissions are matched against `<all_urls>`-style
`content_scripts`/`host_permissions` declarations and, for MV3, subject to
the **OriginControls** system,
`toolkit/components/extensions/ExtensionPermissions.sys.mjs:605-736` (see
`hasMV3RequestedOrigin`, lines 617-635, and `getState`, lines 656-736).
The doc comment on `hasMV3RequestedOrigin` (lines 613-616) states this
mechanism, while written for MV3's additional checks, is "technically not
strictly MV3 specific." Optional permissions (including optional host
permissions) are persisted via `ExtensionPermissions.add/remove()`,
`ExtensionPermissions.sys.mjs:431-492`, called from the `permissions.request()`
implementation path (`OriginControls.setAlwaysOn`/`setWhenClicked`,
lines 769-878, are the runtime per-site grant/revoke UI entry points).

### WebKit

There is **no engine-level auto-grant at all**. `WKWebExtensionContext.h`
states outright: "Permissions in this dictionary should be explicitly
granted by the user before being added,"
`Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionContext.h:256-257` (for
`grantedPermissions`) and lines 266-268 (identical language for
`grantedPermissionMatchPatterns`). `WebExtensionContext::load()`
(`WebExtensionContextCocoa.mm:276-338`) does not grant any permissions; it
only reads back previously-stored grants
(`readStateFromStorage()`, line 294) and injects content for whatever is
already in `m_grantedPermissionMatchPatterns`. The embedding native app is
responsible for presenting the manifest's required permissions to the user
(e.g. at install/update) and setting `grantedPermissions`/
`grantedPermissionMatchPatterns` accordingly; nothing in the engine forces
this to happen automatically. Optional permissions go through the same
`grantedPermissions`/`grantedPermissionMatchPatterns` properties via
`permissionsRequest()`,
`Source/WebKit/UIProcess/Extensions/Cocoa/API/WebExtensionContextAPIPermissionsCocoa.mm:94-145`,
which itself notes in a comment "This matches Chrome and Firefox" for the
zero-permissions-requested short-circuit (line 99).

**Finding for the spec**: Chromium and Gecko silently grant required
host_permissions at install and allow the user (browser UI, not the
extension) to subsequently downgrade specific origins to a runtime-request
state. WebKit inverts this: nothing is granted until something (normally
the embedding app, prompting the user) explicitly grants it -- there is no
engine-guaranteed install-time default. This is a genuine three-way
difference in default behavior, not just naming; flagged as an Issue in
draft.bs.

## 4. activeTab: what it grants, for how long, which gestures activate it

### Chromium

`ActiveTabPermissionGranter::GrantIfRequested()`,
`extensions/browser/permissions/active_tab_permission_granter.cc:134-194`.
Grants (if the extension has the `activeTab` API permission, OR has a
withheld host permission matching the tab's URL, line 152-155): a
tab-specific host permission for the tab's current URL (via
`new_hosts.AddOrigin(...)`, line 168), the `tabs` API permission for that
tab (line 170), and (if the extension has `declarativeNetRequest*`)
`declarativeNetRequestFeedback` (lines 172-176). This is installed via
`UpdateTabSpecificPermissions` (line 187) and also updates the
`CorsOriginAccessList` for that context (`SetCorsOriginAccessList`, line
189-192, calling into `NetworkPermissionsUpdater`).

Granted by (all call `GrantIfRequested`):
- Clicking the extension's toolbar action,
  `chrome/browser/extensions/extension_action_runner.cc:164`.
- A keyboard command,
  `chrome/browser/extensions/extension_keybinding_registry.cc:255`.
- A context-menu item click, `chrome/browser/extensions/menu_manager.cc:787`.
- The omnibox, `chrome/browser/extensions/api/omnibox/omnibox_api.cc:164`.

Lifetime: cleared on `WebContentsDestroyed()` and on
`DidFinishNavigation()` when the navigation is a committed, cross-document,
primary-main-frame, **cross-origin** navigation (`IsSameOrigin()` check),
`active_tab_permission_granter.cc:242-259`. Same-origin navigation, and any
sub-frame navigation, does not revoke it.

### Gecko

`TabManagerBase.addActiveTabPermission(nativeTab)`,
`toolkit/components/extensions/parent/ext-tabs-base.js:2177-2189`: if the
extension has the `activeTab` API permission, OR (`originControls` is on
and the URL is already in `optionalOrigins`), sets
`tab.activeTabWindowID = tab.innerWindowID`. `hasActiveTabPermission`
getter, `ext-tabs-base.js:212-217`, is true only while
`activeTabWindowID === innerWindowID` (i.e. the permission is scoped to
one specific document instance, not a URL pattern). The source comment at
lines 2185-2187 states explicitly: "Note that, unlike Chrome, we don't
currently clear this permission with the tab navigates. If the inner
window is revived from BFCache before we've granted this permission to a
new inner window, the extension maintains its permissions for it" -- i.e.
Gecko's activeTab lifetime is tied to the *inner window* surviving (which
includes bfcache), not to same-origin-vs-cross-origin navigation the way
Chromium's is. It is revoked via `revokeActiveTabPermission()`,
`ext-tabs-base.js:2199-2201`, called from
`ExtensionActions.sys.mjs:225` when a different toolbar action is invoked
on the tab (browser-action UI implementation detail, not a navigation
event).

Granted by: browserAction/pageAction click
(`browser/components/extensions/parent/ext-browserAction.js:733`,
`ext-pageAction.js:114`), omnibox
(`browser/components/extensions/parent/ext-omnibox.js:47`), context menu
(`browser/components/extensions/parent/ext-menus.js:418`), keyboard
command (`browser/components/extensions/parent/ext-commands.js:19`).

### WebKit

`WebExtensionContext::userGesturePerformed(WebExtensionTab&)`,
`WebExtensionContextCocoa.mm:2262-2308`. No-op unless the extension has the
`activeTab` permission (line 2270-2271) and
`tab.shouldGrantPermissionsOnUserGesture()` (line 2273). On success it
creates a match pattern for the tab's *current URL*
(`WebExtensionMatchPattern::getOrCreate(currentURL)`, line 2299) and stores
it as `tab.temporaryPermissionMatchPattern` (line 2300); this pattern
participates directly in `permissionState()`'s tab-temporary-pattern check
(`WebExtensionContext.cpp:880-883`).

Granted by: `performAction()` (toolbar button, user-triggered),
`performCommand()` (keyboard shortcut), `performMenuItem()` (context
menu), and the extension sidebar,
`WebExtensionContextCocoa.mm:1888,2038,2142`;
`WebExtensionSidebarCocoa.mm:489`.

Lifetime: cleared in `clearUserGesture()`,
`WebExtensionContextCocoa.mm:2321-2331`, called from
`didCommitLoadForFrame()` when the main frame commits a URL that the
existing `temporaryPermissionMatchPattern` no longer matches
(`WebExtensionContextCocoa.mm:1639-1642`) -- i.e. scoped to the granted
match pattern (host + scheme, not necessarily exact document identity),
closer to Chromium's model than Gecko's.

**Finding for the spec**: all three engines require the same class of user
gesture (toolbar action, keyboard command, context menu item, plus the
omnibox in Chromium and Gecko) and require `activeTab` to be declared. All
three revoke on navigation away from the granted host/origin, but the
exact revocation trigger differs: Chromium revokes on cross-origin
main-frame navigation; WebKit revokes when the committed URL no longer
matches the granted pattern (functionally similar to Chromium); Gecko
explicitly does NOT revoke on navigation (only when the extension action
requests a fresh grant for a different tab, or the window/tab is torn
down) -- the Gecko source comment names this exact divergence from Chrome.
This is a three-way (effectively two-way, Chromium/WebKit vs. Gecko)
difference worth an Issue line.

## 5. Subdomain implication and restricted hosts/schemes per engine

Subdomain matching itself (`*.example.com` vs `example.com`) is match
pattern grammar -- out of scope per the coordination note; owned by the
sibling "Match patterns" section. What follows is engine-specific
restricted-host/scheme data that is NOT pattern grammar: hosts a host
permission can never cover regardless of how it's written.

### Chromium

- Valid extension URL-pattern schemes:
  `URLPattern::SchemeMasks` enumerates `SCHEME_HTTP`, `SCHEME_HTTPS`,
  `SCHEME_FILE`, `SCHEME_FTP`, `SCHEME_CHROMEUI`, `SCHEME_EXTENSION`,
  `SCHEME_FILESYSTEM`, `SCHEME_WS`, `SCHEME_WSS`, `SCHEME_DATA`,
  `SCHEME_UUID_IN_PACKAGE`, `extensions/common/url_pattern.h:52-64`
  (`SCHEME_ALL` exists but is documented as dangerous and not
  extension-reachable by default, lines 65-72).
- `chrome://` pages: blocked unless
  `--extensions-on-chrome-urls`,
  `extensions/common/permissions/permissions_data.cc:157-162`. Even when
  allowed, MV3 extensions get zero permitted chrome-scheme hosts
  (`ChromeExtensionsClient::GetPermittedChromeSchemeHosts`, returns empty
  for `manifest_version() >= 3`,
  `chrome/common/extensions/chrome_extensions_client.cc:129-141`); MV2
  extensions may be granted only `chrome://favicon`
  (`chrome_extensions_client.cc:139-140`).
- The extension gallery (Chrome Web Store): always blocked for scripting,
  regardless of manifest version or flags --
  `ChromeExtensionsClient::IsScriptableURL` rejects
  `extension_urls::IsWebstoreDomain(url)` unconditionally,
  `chrome_extensions_client.cc:148-157`. Webstore domains:
  `chrome.google.com/webstore` and `chromewebstore.google.com`,
  `extensions/common/extension_urls.cc:41-42,145-147`.
- Cross-extension access: `chrome-extension://` URLs whose host isn't the
  requesting extension's own ID are blocked unless
  `--extensions-on-extension-urls`,
  `permissions_data.cc:164-170`.
- `<all_urls>` never implies the chrome:// or extension-gallery
  restrictions above; those are checked independently of whether the
  pattern matched (`IsRestrictedUrl` runs unconditionally inside
  `CanRunOnPage`, `permissions_data.cc:664-666`, before the pattern-match
  checks).

### Gecko

- Valid moz-extension permission target: any host the granted
  `MatchPatternSet` covers, gated by `CanAccessURI`,
  `WebExtensionPolicy.cpp:325-349`.
- **Restricted domains** (AMO-and-Mozilla-accounts allowlist, engine
  cannot script or otherwise access these regardless of granted host
  permissions): literal pref value
  `accounts-static.cdn.mozilla.net,accounts.firefox.com,addons.cdn.mozilla.net,addons.mozilla.org,api.accounts.firefox.com,content.cdn.mozilla.net,discovery.addons.mozilla.org,oauth.accounts.firefox.com,profile.accounts.firefox.com,support.mozilla.org,sync.services.mozilla.com`,
  `modules/libpref/init/all.js:3133`, pref name
  `extensions.webextensions.restrictedDomains`,
  `toolkit/components/extensions/ExtensionPolicyService.cpp:57`, enforced
  via `WebExtensionPolicy::IsRestrictedURI`,
  `WebExtensionPolicy.cpp:640-651`.
- **Quarantined domains**: a second, separately-configurable list
  (`extensions.quarantinedDomains.list` pref,
  `ExtensionPolicyService.cpp:59`) that individual extensions can be
  exempted from via `mIgnoreQuarantine`
  (`WebExtensionPolicy.h:139-146`, set from
  `aInit.mIsPrivileged || aInit.mIgnoreQuarantine`,
  `WebExtensionPolicy.cpp:223`) -- i.e. this restriction is
  per-installation/build-configured, not hardcoded, and privileged
  extensions bypass it.
- `AddonManagerWebAPI::IsValidSite()` is also folded into
  `IsRestrictedURI` (`WebExtensionPolicy.cpp:648-650`) -- an additional
  restriction source not further chased in this pass (out of scope: it's
  about which sites may call the `mozAddonManager` web API, not about
  host-permission URL matching per se, but it does make those sites
  unreachable via `CanAccessURI`).
- No engine-level chrome://-analog restriction was found gating on
  `<all_urls>` specifically beyond the generic restricted/quarantined
  domain lists above and the standard scheme allowlist implicit in
  `MatchPattern` parsing (sibling section's territory).

### WebKit

- Valid/supported schemes: `*`, `http`, `https`, `file`, `ftp`,
  `webkit-extension` (valid); `*`, `http`, `https`, `webkit-extension`
  (`supportedSchemes`, i.e. what `<all_urls>` / `*://*/*`-style patterns
  can expand to), `Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.cpp:56-65`.
- No gallery/App-Store-domain restriction analogous to Chromium's
  webstore block or Gecko's AMO restricted-domains list was found
  anywhere under `Source/WebKit/UIProcess/Extensions/` or
  `Source/WebKit/Shared/Extensions/`. Broadened beyond those two
  directories: a case-insensitive search of all of `Source/WebKit/` and
  `Source/WebCore/` for `restrictedDomain`, `AllowedDomains`, "app store",
  and "notariz" turns up nothing extension-related either. **This is a
  determinate finding, not an unconfirmed one**: Safari Web Extensions are
  distributed and reviewed through the App Store/notarization process
  rather than a web-reachable extension gallery a content script could
  target, so there is no equivalent surface for the engine to protect at
  the URL-matching layer, and none exists. draft.bs's restricted-URLs list
  already covers this with its generic "the extension's own store or
  gallery, if the implementation has one" clause -- that clause is
  accurate for WebKit as written, since WebKit has none, and needs no
  WebKit-specific addition.
- `isURLForAnyExtension()`,
  `Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:149-151`,
  restricts scripting of *any* `webkit-extension://` URL (not just other
  extensions' -- the check is scheme-based) unless it is the extension's
  own (`isURLForThisExtension`, lines 144-147, checked ahead of any
  pattern match in `permissionState()`, line 871).

## Open / unresolved points (not enough source evidence in this pass)

1. Exact semantics of "explicit" vs "implicit" grant distinctions
   (`aExplicit` parameter in Gecko's `CanAccessURI`, `Explicitly` vs
   `Implicitly` suffixes in WebKit's `PermissionState`) were read enough
   to confirm the enum shape but not traced to every call site; the draft
   avoids asserting fine-grained behavior here beyond what's cited.
2. Chromium's "user-level site blocking" (`IsUrlBlockedByUser`,
   `policy_blocked_hosts`/`policy_allowed_hosts` enterprise policy) and
   Gecko's per-extension `quarantine` opt-out are real engine features
   that interact with host permissions but are policy/enterprise-admin
   surfaces, not something an extension manifest controls; deliberately
   left out of the normative draft text and only mentioned as Issues,
   since the working group would need to decide whether such
   browser/enterprise-level restrictions belong in this spec at all.

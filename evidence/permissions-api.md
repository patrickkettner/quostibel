# `permissions` API: three-way source validation

Read only, no builds, against the Chromium, WebKit and Gecko source trees as checked
out on 2026-09-03. Every claim below cites the file and line read.

## 0. Source files read

Chromium:
- `chrome/common/extensions/api/permissions.json` (the declared schema; not
  `extensions/common/api/permissions.json`, which does not exist)
- `chrome/browser/extensions/api/permissions/permissions_api.h`
- `chrome/browser/extensions/api/permissions/permissions_api.cc`
- `chrome/browser/extensions/api/permissions/permissions_api_helpers.cc`
- `chrome/browser/extensions/api/permissions/permissions_event_router.cc`
- `extensions/browser/permissions/permissions_updater.cc`
- `extensions/common/permissions/permissions_data.h`
- `extensions/browser/permissions/scripting_permissions_modifier.cc`
- `chrome/browser/extensions/api/developer_private/developer_private_functions.cc`
- `chrome/common/extensions/api/_api_features.json`

Gecko:
- `toolkit/components/extensions/schemas/permissions.json`
- `toolkit/components/extensions/parent/ext-permissions.js`
- `toolkit/components/extensions/ExtensionPermissions.sys.mjs`
- `toolkit/components/extensions/Extension.sys.mjs`
- `toolkit/components/extensions/Schemas.sys.mjs`

WebKit:
- `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl`
- `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIPermissionsCocoa.mm`
- `Source/WebKit/UIProcess/Extensions/Cocoa/API/WebExtensionContextAPIPermissionsCocoa.mm`
- `Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm` (requestPermissions,
  requestPermissionMatchPatterns)
- `Source/WebKit/WebProcess/Extensions/Bindings/Scripts/CodeGeneratorExtensions.pm` (what
  `MainWorldOnly` actually does)

## 1. Signature identity: partially holds, not fully

`contains`, `getAll`, `remove`, `onAdded`, `onRemoved` are signature-identical across the
three engines: same parameter shape, same `Permissions {permissions, origins}` dictionary
core, same resolved value types (boolean for `contains`/`remove`, `Permissions` object for
`getAll`, `Permissions` object as event payload).

`request()` is NOT signature-identical once you look past the parameter list:

- Firefox's `Permissions` dictionary carries a third member, `data_collection`, that neither
  Chrome nor WebKit has (`toolkit/components/extensions/schemas/permissions.json:26-31`, vs
  `chrome/common/extensions/api/permissions.json:11-27` and
  `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl:26-29`, neither
  of which declares it).
- Firefox's schema types `permissions` in `Permissions` and `AnyPermissions` as a closed choice
  of `manifest.OptionalPermission`/`manifest.OptionalOnlyPermission` (`permissions.json:9-19`,
  `:38-48`); Chrome's schema types the same field as a bare `array<string>` with no enum
  (`chrome/common/extensions/api/permissions.json:14-19`). This changes error surface (see
  section 3).
- Firefox's `request()` is reachable from content scripts; Chrome's and WebKit's are not (see
  section 5).

## 2. `request()` behavior

### User gesture

- **Chrome**: explicit runtime check. `if (!user_gesture() && !ignore_user_gesture_for_tests &&
  extension_->location() != mojom::ManifestLocation::kComponent) return
  RespondNow(Error(kUserGestureRequiredError));`
  (`chrome/browser/extensions/api/permissions/permissions_api.cc:319-323`). Component
  (built-in) extensions are exempt.
- **WebKit**: explicit runtime check, `WebCore::UserGestureIndicator::processingUserGesture()`,
  reported through the callback/promise machinery rather than a thrown exception
  (`Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIPermissionsCocoa.mm:104-108`).
- **Firefox**: the schema declares `"requireUserInput": true`
  (`toolkit/components/extensions/schemas/permissions.json:106-110`), but the implementation
  itself in `ext-permissions.js` never inspects gesture state; user-gesture enforcement for
  `requireUserInput` functions is generic binding-layer behavior, not something visible in
  `ext-permissions.js`. Not independently confirmed in the files read for this task; flagged as
  undetermined below.

### Active window requirement

- **Chrome**: requires a native window and errors if none exists, independent of the gesture
  check: `gfx::NativeWindow native_window = ChromeExtensionFunctionDetails(this)
  .GetNativeWindowForUI(); if (!native_window && ...) return RespondNow(Error("Could not find
  an active window."));` (`permissions_api.cc:325-329`).
- **WebKit**: no equivalent check in the extension-API layer. `requestPermissions()` and
  `requestPermissionMatchPatterns()` pass `tab = nullptr` when called from
  `permissionsRequest()` (`Source/WebKit/UIProcess/Extensions/Cocoa/API/
  WebExtensionContextAPIPermissionsCocoa.mm:145,152`), and if the embedding app's delegate
  doesn't implement the prompt selector, or simply never calls its completion handler, the
  request is silently denied after a fixed 2-minute timeout: `static constexpr auto
  permissionRequestTimeout = 2_min;` with a `dispatch_after` that resolves the aggregator to an
  empty allowed set (`Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm:113,
  751-756`). No "no active window" error exists in WebKit's source for this path.
- **Firefox**: no active-window check either. The prompt goes out as an observer notification
  (`webextension-optional-permission-prompt`) carrying whatever browser element is available
  (`context.pendingEventBrowser || context.xulBrowser`,
  `toolkit/components/extensions/parent/ext-permissions.js:189-205`); nothing in this file
  requires a foreground window to exist.

This is a genuine three-way divergence: only Chrome treats "no active window" as a hard error
distinct from "no user gesture."

### Called from a content script

- **Chrome**: cannot happen. The entire `permissions` namespace is scoped to
  `"contexts": ["privileged_extension"]` in
  `chrome/common/extensions/api/_api_features.json:810-819`. Content scripts do not get
  `chrome.permissions` at all.

  This `contexts` restriction is a separate axis from feature reachability (whether an ordinary
  extension can use the namespace at all, versus which contexts within an already-permitted
  extension can call it). A feature file's `contexts` field alone does not establish that the
  namespace is reachable by an ordinary extension: a feature's `dependencies` can chain through
  permission, manifest, and behavior features, any one of a list of alternatives can satisfy a
  dependency, and each alternative can carry further dependencies of its own, so a single feature
  file can misrepresent reachability the same way a single IDL file misrepresented a path above.
  Reachability for `permissions`, `permissions.request`, and `permissions.getAll` was checked
  with `python3 ~/crx-audit/harness/lib/feature_reachability.py <key>`, which walked the
  dependency graph and confirmed each is `REACHABLE by an ordinary extension` with no
  allowlist-style gate, consistent with the content-script exclusion above being a `contexts`
  restriction rather than a reachability gate. No other reachability claim in this document
  rests on a feature file read in isolation.
- **WebKit**: cannot happen either, but for a different mechanism. The whole
  `WebExtensionAPIPermissions` IDL interface is marked `MainWorldOnly`
  (`Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl:31-35`).
  `MainWorldOnly` on an interface makes every property conditional on
  `impl->isForMainWorld()` at the JS-binding level
  (`Source/WebKit/WebProcess/Extensions/Bindings/Scripts/CodeGeneratorExtensions.pm:424`,
  `:1771,1781-1783`), which is false for a content-script isolated world.
- **Firefox**: `request()` specifically is exposed to content scripts.
  `toolkit/components/extensions/schemas/permissions.json:105-110` sets
  `"allowedContexts": ["content"]` on the `request` function only; `getAll`, `contains`,
  `remove`, `onAdded`, `onRemoved` carry no such override and fall back to the namespace's
  default (privileged/background) contexts (`InjectionEntry.allowedContexts` getter,
  `toolkit/components/extensions/Schemas.sys.mjs:819-828`).

This is the sharpest three-way split found in this API: Chrome and WebKit exclude the entire
namespace from content scripts by two unrelated mechanisms; Firefox deliberately carves out
`request()` alone for content-script use.

### Called from a background service worker with no active window

Undetermined from source read for this task in the Chrome/MV3 case beyond what's stated above:
`GetNativeWindowForUI()` (`permissions_api.cc:326`) resolves to some browser window associated
with the profile if one exists anywhere, not necessarily one owned by the caller. A background
service worker in a browser with at least one open window would not hit the "no active window"
error; one with literally no browser windows open would. Not traced further into
`ChromeExtensionFunctionDetails::GetNativeWindowForUI()` itself.

### Already granted

All three resolve `true` immediately without prompting when everything requested is already
active:
- Chrome: `if (total_new_permissions->IsEmpty()) { constexpr bool granted = true; return
  RespondNow(WithArguments(granted)); }` (`permissions_api.cc:400-403`).
- Firefox: after filtering out already-granted items, `if (!permissions.length && !origins.length
  && !data_collection.length) return true;` (`ext-permissions.js:181-187`).
- WebKit: `if (hasPermissions(permissions, matchPatterns)) { completionHandler(true); return; }`
  (`WebExtensionContextAPIPermissionsCocoa.mm:105-108`).

### Resolve false vs. reject on denial

All three resolve `false` (not a rejection) when the user declines the prompt:
- Chrome: `if (payload.result != ExtensionInstallPrompt::Result::ACCEPTED) { Respond(ArgumentList(
  api::permissions::Request::Results::Create(false))); return; }` (`permissions_api.cc:498-501`).
- Firefox: `if (!(await allowPromise)) { return false; }` (`ext-permissions.js:212-214`).
- WebKit: the `CallbackAggregator` in `permissionsRequest()` calls `completionHandler(false)`
  when either the permissions or match-pattern grant did not fully succeed
  (`WebExtensionContextAPIPermissionsCocoa.mm:133-137`).

Validation failures (bad permission name, bad origin, not declared in the manifest) reject the
promise / raise a callback error in all three instead:
- Chrome: `RespondNow(Error(...))` for unknown permission
  (`permissions_api_helpers.cc:104-108`) or unlisted manifest permission
  (`permissions_api.cc:349-354`), which the extension-function/promise plumbing turns into a
  rejection.
- Firefox: `throw new ExtensionError(...)` for not-declared permissions or origins
  (`ext-permissions.js:112-116, 130-136`).
- WebKit: `callback->reportError(...)`, explicitly commented "Chrome reports this error as
  callback error and not an exception, so do the same"
  (`WebExtensionAPIPermissionsCocoa.mm:99-101, 105-106, 111-114`), which rejects the promise via
  `WebExtensionCallbackHandler::reportError` (`Source/WebKit/WebProcess/Extensions/Bindings/
  JSWebExtensionWrapper.cpp:134-149`, rejecting when a promise `m_rejectFunction` is present).

### Enterprise/managed policy blocking

- Chrome: explicit check, `kBlockedByEnterprisePolicy`, via
  `ExtensionManagementFactory::GetForBrowserContext(...)->IsPermissionSetAllowed(...)`
  (`permissions_api.cc:406-410`).
- Firefox: explicit check against `Services.policies?.getExtensionSettings(extension.id)
  ?.blocked_permissions`, matching Chrome's error string
  ("Permissions are blocked by enterprise policy.") on purpose per the adjoining comment
  (`ext-permissions.js:150-165`).
- WebKit: no equivalent found. Grepped both `.mm` files read for `policy`/`Policy`; no matches.
  Undetermined whether WebKit enforces managed configuration for optional permission requests
  through some other layer not read for this task (e.g. an MDM profile mechanism outside
  `Source/WebKit/*/Extensions`); the two files that implement `permissionsRequest()` contain no
  such check.

### Granting host permissions beyond `optional_host_permissions`

All three agree here -- this is a point of agreement, not divergence. A requested origin must be
subsumed by the extension's declared optional (or required-but-withheld) host permissions in all
three engines:
- Chrome: unlisted origins are collected into `unlisted_hosts` and rejected with
  `kNotInManifestPermissionsError` (`permissions_api_helpers.cc:200-226`,
  `permissions_api.cc:349-354`).
- Firefox: `if (!optionalOrigins.subsumes(new MatchPattern(origin))) throw new ExtensionError(...
  was not declared in the manifest)` (`ext-permissions.js:129-136`), and the same check again
  inside `ExtensionPermissions.normalizeOptional` (`ExtensionPermissions.sys.mjs:374-381`,
  throw at `:380`).
- WebKit: `verifyRequestedPermissions()` builds `allowedHostPermissions` from
  `extension->allRequestedMatchPatterns()` plus `extension->optionalPermissionMatchPatterns()`
  and rejects any requested pattern with no match
  (`WebExtensionAPIPermissionsCocoa.mm:178-224`).

## 3. The `Permissions` dictionary

### Permission-string validation and error mode for unrecognized strings

- **Chrome**: no schema-level enum. `chrome/common/extensions/api/permissions.json:11-19`
  types `permissions` as a plain `array<string>`. Validation is entirely inside
  `UnpackAPIPermissions()`: an unrecognized name produces `kUnknownPermissionError` and
  `UnpackPermissionSet()` returns `nullptr`, which every caller (`contains`, `request`,
  `remove`) turns into `RespondNow(Error(...))`, i.e. a promise **rejection**
  (`permissions_api_helpers.cc:100-111`).
- **Firefox**: schema-level enum. `permissions.json:9-19` (`request`/`remove`/events) and
  `:38-48` (`getAll`/`contains`) type the `permissions` array as a closed choice of manifest
  permission enums. A string outside that enum fails schema/binding validation before
  `ext-permissions.js` ever runs, which is a synchronous **throw**, not a promise rejection
  (behavior of the generic Schemas.sys.mjs argument validator; not itself read in the files
  listed for this task beyond confirming the enum typing).
- **WebKit**: `contains()` throws synchronously for an unrecognized permission name --
  `validatePermissionsDetails()` sets `outExceptionString` directly and `contains` is declared
  `[RaisesException]` with no workaround
  (`WebExtensionAPIPermissionsCocoa.mm:66-83, 230-250`). `request()` and `remove()` hit the same
  `validatePermissionsDetails()` but explicitly route the failure through
  `callback->reportError(...)` instead of the exception path, with the comment "Chrome reports
  this error as callback error and not an exception, so do the same"
  (`WebExtensionAPIPermissionsCocoa.mm:98-101, 132-136`) -- i.e. WebKit deliberately makes
  `contains()` behave differently (sync throw) from `request()`/`remove()` (rejection) for the
  same kind of bad input.

Net: three different error shapes for "you passed a permission string the engine doesn't
recognize at all" depending on engine and, in WebKit's case, depending on which of the three
functions you called.

### Unknown-but-syntactically-valid permission not requested by the extension

All three agree `contains()` returns `false` rather than erroring when the string is a real
permission name but the extension didn't declare it:
- Chrome: folded into the `has_all_permissions` boolean via `unpack_result->unlisted_apis`
  (`permissions_api.cc:171-192`) -- no error thrown for `contains`.
- Firefox: `if (!context.extension.hasPermission(perm)) return false;`
  (`ext-permissions.js:227-232`).
- WebKit: `hasPermissions()` simply returns false; the exception path in
  `validatePermissionsDetails()` only fires for names outside
  `WebExtension::supportedPermissions()` altogether
  (`WebExtensionAPIPermissionsCocoa.mm:66-83, 233-236`).

### `origins` match-pattern grammar

All three reuse the same match-pattern parser used for manifest host permissions, confirmed
directly from source:
- Chrome: `URLPattern explicit_origin(Extension::kValidHostPermissionSchemes); ...
  explicit_origin.Parse(origin_str)` (`permissions_api_helpers.cc:139-146, 178-188`) -- the same
  `URLPattern` class and scheme set manifest `host_permissions` parsing uses.
- Firefox: `new MatchPattern(origin, {...})` / `manifest.MatchPattern` schema `$ref`
  (`permissions.json:20-25`, `ext-permissions.js:130-136`) -- the same `MatchPattern` class used
  for manifest permissions elsewhere in the tree.
- WebKit: `WebExtensionMatchPattern::getOrCreate(origin)`
  (`WebExtensionAPIPermissionsCocoa.mm:239-247`) -- the same match-pattern class
  `verifyRequestedPermissions()` uses against the manifest's `allRequestedMatchPatterns()`.

A syntactically invalid pattern rejects/throws in all three (Chrome:
`kInvalidOrigin`/`ErrorUtils::FormatErrorMessage`, `permissions_api_helpers.cc:181-186`;
Firefox: implicit `MatchPattern` constructor failure surfaces as a schema/argument error, not
independently traced; WebKit: `!pattern || !pattern->isSupported()` produces `outExceptionString`
`... is not a valid pattern"`, `WebExtensionAPIPermissionsCocoa.mm:240-244`).

Chrome's schema comment explicitly documents path-stripping: "Paths on origin patterns will be
ignored" (`chrome/common/extensions/api/permissions.json` function description on `request`).
Not independently re-derived from the parsing code for Firefox/WebKit in this pass; treated as
documented-but-engine-specific.

### `data_collection`

Confirmed present only in Firefox, and pref-gated even there:
- `permissions.json:26-31` (`Permissions`) and `:55-60` (`AnyPermissions`) declare
  `data_collection: array<manifest.OptionalDataCollectionPermission>`.
- `ext-permissions.js:19-24` reads `extensions.dataCollectionPermissions.enabled` (default
  `false`) into `dataCollectionPermissionsEnabled`; `normalizePermissions()` deletes the
  `data_collection` field entirely when the pref is off (`ext-permissions.js:41-46`).
- `request()`, `contains()`, and `remove()` in `ext-permissions.js` all gate their
  `data_collection` handling behind the same pref (`:117-148, 177-184, 244-250`).
- Neither Chrome's `chrome/common/extensions/api/permissions.json` nor WebKit's
  `WebExtensionAPIPermissions.idl:26-29` (`dictionary WebExtensionPermissions { sequence<DOMString>
  origins; sequence<DOMString> permissions; };`) has any such field.

## 4. `getAll()`

Contrary to the task's stated hypothesis that this is a likely silent divergence toward
"optional-only", **Chrome and Firefox agree** that `getAll()` returns the union of required
manifest permissions and granted optional/runtime permissions, not just the optional set:

- Chrome: `getAll()` returns `extension()->permissions_data()->active_permissions()`
  (`permissions_api.cc:202-206`). `active_permissions()` is populated by
  `PermissionsUpdater::InitializePermissions()` from "desired permissions", which starts from
  `PermissionsParser::GetRequiredPermissions()` bounded by grants
  (`extensions/browser/permissions/permissions_updater.cc:558-599`) -- i.e. required permissions
  are always in `active_permissions()`.
- Firefox: `getAll()` returns `context.extension.activePermissions`
  (`ext-permissions.js:221-225`), whose getter doc-comment is explicit: "Returns an object
  representing all capabilities this extension has access to, **including fixed ones from the
  manifest** as well as dynamically granted permissions" (`Extension.sys.mjs:1388-1411`).

WebKit's `getAll()` does the same union (`currentPermissions()` /
`currentPermissionMatchPatterns()`, `WebExtensionContextAPIPermissionsCocoa.mm:52-58, 61-68`),
but adds a behavior neither Chrome nor Firefox's read files show: if the extension has been
granted enough origin access that it effectively covers all hosts, but the manifest itself never
declared a literal all-hosts pattern (e.g. broad access assembled from `tabs`/`webNavigation`-style
implicit grants), `getAll()` **synthesizes** and appends the all-hosts-and-schemes match pattern
to `origins` rather than reporting the narrower, technically-accurate set:

```
if (hasGrantedAccessToAllURLsOrHosts) {
    ...
    // If we don't have the all URLs and hosts match pattern(s) in the manifest,
    // access was requested implicitly (tabs, web navigation, etc.).
    if (!appendedMatchAllURLsOrHostsPattern)
        origins.append(WebExtensionMatchPattern::allHostsAndSchemesMatchPattern()->string());
}
```
(`WebExtensionContextAPIPermissionsCocoa.mm:70-84`).

This is the getAll() divergence: all three include required manifest permissions (agreement),
but WebKit additionally reports an implicit "all hosts" origin under conditions where Chrome and
Firefox would report only the origins actually declared/granted.

## 5. `onAdded` / `onRemoved`

### Firing on browser-UI-driven changes, not just API calls

Confirmed for Chrome: the same `PermissionsUpdater` / `NotifyPermissionsUpdated` /
`PermissionsManager` / `PermissionsEventRouter` pipeline that backs `permissions.request()` and
`permissions.remove()` is also used by:
- `chrome://extensions` "site access" UI, via
  `DeveloperPrivateAddHostPermissionFunction::Run()` calling
  `PermissionsUpdater(...).GrantRuntimePermissions(...)`
  (`chrome/browser/extensions/api/developer_private/developer_private_functions.cc:1270-1300`).
- The extension-icon "on this site"/"on all sites" toggle and related withheld-host-permission UI,
  via `ScriptingPermissionsModifier`, which calls both `GrantRuntimePermissions()` and
  `RevokeRuntimePermissions()` from user-driven code paths
  (`extensions/browser/permissions/scripting_permissions_modifier.cc:176-230`).

Both paths funnel into `PermissionsUpdater::NotifyPermissionsUpdated()`
(`extensions/browser/permissions/permissions_updater.cc:664-683`), which maps to
`PermissionsManager::UpdateReason::kAdded`/`kRemoved` and fires the `onAdded`/`onRemoved` events
through `PermissionsEventRouter::OnExtensionPermissionsUpdated()`
(`chrome/browser/extensions/api/permissions/permissions_event_router.cc:34-67`) -- so yes, a user
toggling site access in Chrome's UI fires `onAdded`/`onRemoved` in the extension exactly as if
the extension had called `permissions.request()`/`remove()` itself.

One explicit exception in Chrome: policy-driven permission changes do **not** fire either event.
`case PermissionsManager::UpdateReason::kPolicy: // Explicitly don't trigger onAdded and
onRemoved for policy-related events. return;`
(`permissions_event_router.cc:50-53`).

Not independently re-traced for Firefox or WebKit in this pass beyond what the schema/API files
show: Firefox's event handlers listen for the generic `"change-permissions"` `Management` event
(`ext-permissions.js:50-99`), which is emitted by `ExtensionPermissions.add()`/`.remove()`
(`ExtensionPermissions.sys.mjs:476, 541`) -- those are called from the API implementation itself,
so whether Firefox's own permission-management browser UI (e.g. about:addons) also funnels
through `ExtensionPermissions.add`/`.remove` (and therefore also fires the events) is
undetermined from the files read here. WebKit's `firePermissionsEventListenerIfNecessary()`
(`WebExtensionContextAPIPermissionsCocoa.mm:173-182`) is called from `permissionsRequest()`
and, per its name, is presumably invoked elsewhere in `WebExtensionContext` for UI-driven grants
too, but those call sites were not located/read in this pass.

### Firing in content scripts

Given section 2's finding that the entire `permissions` namespace (Chrome, WebKit) or everything
except `request()` (Firefox) is excluded from content-script contexts by the same
context/world-restriction mechanisms already cited, `onAdded`/`onRemoved` listeners are not
reachable from a content script in any of the three engines. Not separately re-verified beyond
that inference from the namespace/interface-level restriction already cited in section 2.

## 6. `data_collection`

See section 3. Firefox-only, pref-gated (`extensions.dataCollectionPermissions.enabled`,
default `false`), appears as an optional third array (`OptionalDataCollectionPermission[]`) on
both the `Permissions` dictionary passed to `request`/`remove`/events and the `AnyPermissions`
dictionary returned by `getAll`/`contains`. Confirmed absent from Chrome's schema and WebKit's
IDL dictionary.

## Undetermined / not independently confirmed in this pass

- Firefox's `requireUserInput: true` enforcement mechanism for `request()` -- schema declares it
  (`permissions.json:110`), but the generic binding-layer code that enforces it was not read.
- Chrome's `GetNativeWindowForUI()` semantics when called from a background service worker with
  browser windows open elsewhere in the profile but none belonging to the invoking extension
  page -- not traced past the call site in `permissions_api.cc:326`.
- Whether WebKit enforces any managed/MDM-style block on `permissions.request()` through a layer
  outside `Source/WebKit/*/Extensions` (the two files that implement it show no such check).
- Whether Firefox's or WebKit's user-facing permission-management UI (about:addons; the app's own
  extension settings) fires `onAdded`/`onRemoved` the way Chrome's `chrome://extensions` UI does
  -- only Chrome's UI-to-event path was traced end to end.

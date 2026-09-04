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
- `chrome/browser/extensions/chrome_extension_function_details.cc` (`GetNativeWindowForUI`)
- `tools/json_schema_compiler/model.py` (`ReturnsAsync`/`can_return_promise`)
- `extensions/renderer/bindings/api_signature.cc` (`ParseCallback`,
  `BuildReturnsAsyncFromValues`)
- `extensions/renderer/bindings/api_request_handler.cc` (`GetAsyncResultHandler`)

Gecko:
- `toolkit/components/extensions/schemas/permissions.json`
- `toolkit/components/extensions/parent/ext-permissions.js`
- `toolkit/components/extensions/ExtensionPermissions.sys.mjs`
- `toolkit/components/extensions/Extension.sys.mjs`
- `toolkit/components/extensions/Schemas.sys.mjs`
- `toolkit/components/extensions/ExtensionCommon.sys.mjs` (`LocalAPIImplementation.callAsyncFunction`,
  `wrapPromise`)
- `toolkit/components/extensions/ExtensionWorkerChild.sys.mjs`
- `toolkit/components/extensions/MatchPattern.cpp` (`ignorePath` handling)
- `browser/modules/ExtensionsUI.sys.mjs`
- `browser/components/enterprisepolicies/Policies.sys.mjs`

WebKit:
- `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl`
- `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIPermissionsCocoa.mm`
- `Source/WebKit/UIProcess/Extensions/Cocoa/API/WebExtensionContextAPIPermissionsCocoa.mm`
- `Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm` (requestPermissions,
  requestPermissionMatchPatterns, `permissionsDidChange`, `setGrantedPermissions`)
- `Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp` (`setGrantedPermissions`,
  `permissionState`)
- `Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.h` (`Options`)
- `Source/WebKit/WebProcess/Extensions/Bindings/Scripts/CodeGeneratorExtensions.pm` (what
  `MainWorldOnly` and `ReturnsPromiseWhenCallbackIsOmitted` actually do)

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

## 1a. Trailing callback argument on every method

Verified per browser, per method (`getAll`, `contains`, `request`, `remove`; the two events use
`addListener`/`removeListener`/`hasListener` and are not part of this claim). All three browsers
accept an optional trailing callback function and invoke it instead of resolving a promise when
one is supplied, on all four methods, with no difference between Manifest V2 and Manifest V3.

- **Chrome**: all four methods declare `"returns_async": {"name": "callback", ...}` in the schema
  (`chrome/common/extensions/api/permissions.json`, `getAll` at the `getAll` function block,
  `contains`/`request`/`remove` likewise each with their own `returns_async`), and none of the
  four sets `does_not_support_promises`. `tools/json_schema_compiler/model.py`'s `ReturnsAsync`
  class computes `can_return_promise = json.get('does_not_support_promises') is None`, so all
  four are promise-capable by the schema compiler's own model. At the renderer-binding layer
  (not the schema compiler, which only feeds C++ codegen and documentation), the actual dual
  dispatch is generic and per-call, not per-manifest-version:
  `BuildReturnsAsyncFromValues()` sets `promise_support = kSupported` and `optional = true` for
  any `returns_async` lacking `does_not_support_promises`
  (`extensions/renderer/bindings/api_signature.cc:39-56`). `ArgumentParser::ParseCallback()`
  inspects the actual trailing argument at call time: if a function value was passed, `async_type_
  = kCallback` and that function is invoked; if the argument was omitted and promise support is
  present, `async_type_ = kPromise` (`api_signature.cc:362-393`). `APIRequestHandler::
  GetAsyncResultHandler()` only constructs a `v8::Promise::Resolver` (and thus only returns a
  promise) when `async_type == kPromise`; when a callback was supplied, no promise is created at
  all (`extensions/renderer/bindings/api_request_handler.cc:587-597`, with an explicit `DCHECK`
  that a promise-typed call is never started with a callback also present). None of this is
  gated on `manifest_version`: no such check exists anywhere in `api_signature.cc`,
  `api_binding.cc`, or `api_request_handler.cc`, and the `permissions`, `permissions.getAll`,
  `permissions.contains`, `permissions.request`, and `permissions.remove` feature entries in
  `chrome/common/extensions/api/_api_features.json:809-819` carry no `min_manifest_version` (only
  the unrelated `permissions.addHostAccessRequest`/`removeHostAccessRequest`, MV3-only, do).
  Reachability for `permissions`/`permissions.request` was independently confirmed with
  `python3 ~/crx-audit/harness/lib/feature_reachability.py <key>`: both are `REACHABLE by an
  ordinary extension` with no manifest-version-conditioned path. So Chrome's dual callback/promise
  support for all four methods is uniform across MV2 and MV3, contrary to the common assumption
  that promise support in Chrome's extension APIs is an MV3-only addition; it is a per-function
  schema property, checked generically at bind time, independent of manifest version.
- **Firefox**: all four methods declare `"async": "callback"` in the schema
  (`toolkit/components/extensions/schemas/permissions.json:68,86,109,132`). At the binding layer,
  `FunctionType.parseSchema()` computes `hasAsyncCallback` when the last declared parameter's name
  matches `schema.async` (`Schemas.sys.mjs:2651-2673`), true for all four. The generated stub
  (`FunctionEntry.getDescriptor()`, `Schemas.sys.mjs:3067-3095`) pops the actual last call
  argument as `callback` only `if (this.hasAsyncCallback)`, then calls
  `apiImpl.callAsyncFunction(actuals, callback, this.requireUserInput)`. In
  `LocalAPIImplementation.callAsyncFunction()` (`ExtensionCommon.sys.mjs:1143-1157`), the
  implementation function is invoked and its result wrapped: `return
  this.context.wrapPromise(promise, callback)`. `wrapPromise`'s own doc comment states the
  dispatch plainly: "If callback is null, a promise object belonging to the target scope [is
  returned]. Otherwise, undefined [is returned and callback is invoked]"
  (`ExtensionCommon.sys.mjs:870-871`, implemented `:874-899`). No `manifestVersion` check appears
  anywhere in this call chain (`Schemas.sys.mjs`'s `FunctionType`/`FunctionEntry`,
  `ExtensionCommon.sys.mjs`'s `callAsyncFunction`/`wrapPromise`), so this is uniform across MV2
  and MV3 in Firefox as well.
- **Safari**: `ReturnsPromiseWhenCallbackIsOmitted` is declared once, on the interface itself, not
  per method (`WebExtensionAPIPermissions.idl:33`, in the same attribute block as
  `MainWorldOnly`). All four methods' IDL declarations end with `[Optional, CallbackHandler]
  function callback` as their last parameter (`WebExtensionAPIPermissions.idl:37,40,45,48`).
  `CodeGeneratorExtensions.pm` resolves the attribute per function as `$function->extendedAttributes
  ->{"ReturnsPromiseWhenCallbackIsOmitted"} || $interface->extendedAttributes->
  {"ReturnsPromiseWhenCallbackIsOmitted"}` (line 521), so the interface-level declaration applies
  to every method on it, including all four here. At generation time, `$returnsPromise =
  $callbackHandlerArgument && $returnsPromiseIfNoCallback` (line 729): when true, the generated
  code only builds a deferred JS promise and substitutes it as the callback handler `if
  (!${callbackHandlerArgument})`, i.e. only when the JS caller did not supply one (lines 736-743);
  when a real callback was supplied, that value is used directly and no promise is constructed.
  No `ManifestVersion`-conditioned attribute or check appears anywhere in the `.idl` file or in
  this code path in `CodeGeneratorExtensions.pm`, so this is uniform across whatever manifest
  versions WebKit's extension engine supports.

Conclusion: the claim as stated in the draft ("Chrome, Firefox, and Safari... accept a callback
function as a trailing argument on every method here... instead of returning a promise when
supplied") holds for all three browsers and all four methods, with no manifest-version-specific
exception found in any of the three engines' binding/codegen layers.

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
  itself in `ext-permissions.js` never inspects gesture state. Confirmed generic: `FunctionType`
  parses `requireUserInput` into `this.requireUserInput` (`Schemas.sys.mjs`, `FunctionType`
  constructor) and the generated call stub passes it straight through:
  `apiImpl.callAsyncFunction(actuals, callback, this.requireUserInput)`
  (`Schemas.sys.mjs:3067-3095`, `getDescriptor()`). `LocalAPIImplementation.callAsyncFunction()`
  enforces it before the implementation function is ever called: `if (requireUserInput) { if
  (!this.context.contentWindow.windowUtils.isHandlingUserInput) { throw new ExtensionError(...)
  } }` (`ExtensionCommon.sys.mjs:1143-1149`), then only calls `this.pathObj[this.name](...args)`
  afterward. This is a real gap, not just a caveat: the check reads
  `this.context.contentWindow`, which a Manifest V3 background service worker context does not
  have. `ExtensionWorkerChild.sys.mjs`'s own `callAPIImplementation()` dispatcher carries an
  explicit acknowledgment of this: "TODO (Bug 1728328): follow up to take callAsyncFunction
  requireUserInput parameter into account (until then callAsyncFunction, callFunction and
  callFunctionNoReturn calls do not differ yet)" (`ExtensionWorkerChild.sys.mjs:404-408`), and the
  worker-context call path invokes `impl[requestType](normalizedArgs)` with no
  `requireUserInput` argument at all. So Firefox's `requireUserInput` enforcement is real and
  generic for `permissions.request()` called from a background page/extension page context, but
  is a known, explicitly-commented gap for a call originating from an MV3 background service
  worker.

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

Resolved. `ChromeExtensionFunctionDetails::GetNativeWindowForUI()`
(`chrome/browser/extensions/chrome_extension_function_details.cc:82-138`) tries, in order: (1)
`WindowControllerList::GetInstance()->CurrentWindowForFunction(function_)`; (2) the calling
function's sender `WebContents`, if it supports modal dialogs; (3) on platforms with app windows,
an app window belonging to the same extension; (4) as a last resort, `GetAllBrowserWindowInterfaces()`
filtered to the calling extension's `Profile`, returning the **first** matching window found,
with no requirement that it have any other relationship to the calling extension or context
(`chrome_extension_function_details.cc:120-133`). Only if that loop finds zero browser windows in
the whole profile does the function return an empty `gfx::NativeWindow()`
(`chrome_extension_function_details.cc:136-138`), which is what `permissions_api.cc:326-329`
turns into the "Could not find an active window" rejection. So: a background service worker
calling `permissions.request()` in a profile that has at least one open browser window anywhere
(even one with no relationship to the calling extension) does not hit this error; the error fires
only when the calling extension's entire profile has zero open browser windows.

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
- WebKit: **not in open source**. Beyond the two `.mm` files that implement `permissionsRequest()`
  (already grepped for `policy`/`Policy` with no matches), this pass additionally grepped
  `WebExtensionContext.cpp`/`.h` (the `permissionState()` five-state machine file) and every
  `.cpp`/`.h` file under `Source/WebKit/UIProcess/Extensions/` for `policy`/`Policy`/`MDM`/
  `ManagedConfiguration`. The only hits are unrelated (`content_security_policy` manifest-key
  handling in `WebExtension.cpp`, and a `decidePolicyForNavigationAction` WKUIDelegate method
  unrelated to permissions). No managed/MDM-style permission-blocking mechanism exists anywhere
  in the open-source WebKit extension engine. This is consistent with, not separate from, the
  finding already in the draft text about `AllowedDomains`/`DeniedDomains`: Apple's public MDM
  schema for Safari extensions is host/domain-scoped only, and whatever Safari's application does
  for non-host permissions under a managed policy (if anything) is closed application code, not
  engine behavior. Classified as not in open source rather than left as a bare "undetermined."

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

Firefox does the same, by a different mechanism, confirmed by source: the validation calls in
`ext-permissions.js` (`new MatchPattern(origin)`, e.g. `:131,174,237,261`) parse the origin
path-sensitively, but the storage layer normalizes it away. `ExtensionPermissions.add()`/`.remove()`
call `new MatchPattern(origin, { ignorePath: true }).pattern` before persisting a granted/removed
origin (`ExtensionPermissions.sys.mjs`, both functions). `MatchPatternCore`'s constructor
implements `ignorePath` by truncating the pattern at the end of the host and appending a literal
`/*`, discarding whatever path text was present (`toolkit/components/extensions/MatchPattern.cpp:336-339`).
So a granted Firefox origin permission is always stored with an effective path of `/*`, matching
Chrome's documented behavior in effect, if not in mechanism (Chrome elides the path at the
comparison/grant-computation step; Firefox elides it at storage time by literal truncation).

WebKit does not do this. `WebExtensionMatchPattern::Options` declares `IgnorePaths` as an option
(`Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.h:69`), but it is a *matching*-time
option ("Ignore the path component when matching"), and `verifyRequestedPermissions()`'s call to
`WebExtensionMatchPattern::getOrCreate(origin)` (`WebExtensionAPIPermissionsCocoa.mm:239-247`)
does not pass it -- the pattern is constructed and stored with whatever path the caller wrote,
literally. This was not traced further to confirm whether a literal path in an `origins` entry
changes what gets granted in practice (as opposed to just being stored verbatim); that would
require tracing how the stored pattern is later compared during `permissionState()` checks, which
is out of scope for this bounded check.

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

The synthesized string itself is `*://*/*`, not `<all_urls>`. `allHostsAndSchemesMatchPattern()`
(`WebExtensionMatchPattern.h:85`) resolves to the pattern constant
`static constexpr ASCIILiteral allHostsAndSchemesPattern = "*://*/*"_s;`
(`WebExtensionMatchPattern.cpp:48`, consumed at `:164`), a distinct constant from
`allURLsMatchPattern()`'s `"<all_urls>"_s` (`:47`, `:159`).

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

Resolved for both remaining engines.

**Firefox**: `ExtensionPermissions.add()`/`.remove()` (`ExtensionPermissions.sys.mjs:476,529`,
emitting `Management.emit("change-permissions", ...)` unconditionally whenever anything was
actually added/removed, with no "silent" parameter anywhere in either function's signature) are
called from more than just `ext-permissions.js`. Two non-API call sites confirm both a UI-driven
and a policy-driven path fire the same event:
- **UI-driven**: `browser/modules/ExtensionsUI.sys.mjs:609,616` -- Firefox's user-facing
  extension-permissions UI calls `ExtensionPermissions.add(addon.id, perms)`/
  `ExtensionPermissions.remove(addon.id, perms)` directly. Also,
  `toolkit/components/extensions/ExtensionPermissions.sys.mjs`'s `OriginControls.setAlwaysOn()`
  and `.setWhenClicked()` (the per-site "always allow"/"only when clicked" runtime toggle, i.e.
  Firefox's analogue to Chrome's site-access UI) call `ExtensionPermissions.add()`/`.remove()`
  directly (`ExtensionPermissions.sys.mjs:771-818` and `:826-878`).
- **Policy-driven**: `browser/components/enterprisepolicies/Policies.sys.mjs:1858-1875` --
  applying an enterprise policy's `blocked_permissions` list calls
  `ExtensionPermissions.remove(addon.id, {...}, extension)` directly to revoke any now-blocked,
  previously-granted optional permission. This call goes through the exact same `remove()`
  function as everything else, with no policy-specific suppression of the emitted event.

So in Firefox, both UI-driven and policy-driven permission changes fire `onAdded`/`onRemoved`,
the same as an API call would; Firefox has no analogue of Chrome's explicit policy-case
suppression (see below).

**WebKit**: `firePermissionsEventListenerIfNecessary()` has call sites beyond
`permissionsRequest()`. It is called from `WebExtensionContext::permissionsDidChange()`
(`WebExtensionContextCocoa.mm:632-660`, both the `PermissionsSet` and `MatchPatternSet`
overloads), which is itself called from `WebExtensionContext::setGrantedPermissions()`
(`WebExtensionContext.cpp:283-308`) and the equivalent setters for denied permissions and for
granted/denied match patterns (`WebExtensionContext.cpp:316-341,364-402`), i.e. from the engine
side of the public `WKWebExtensionContext.grantedPermissions`/`.grantedPermissionMatchPatterns`
properties the embedding application sets. `permissionsDidChange()` fires the event whenever the
notification is a "were granted"/"were removed" kind, unconditionally -- there is no
application-driven-vs-API-driven distinction at this layer; any change to those properties, for
any reason the application has, fires the event. (As an aside, the same
`permissionsDidChange()`/`firePermissionsEventListenerIfNecessary()` path is also reached from
`activeTab`'s user-gesture grant and its navigation-triggered revocation,
`WebExtensionContextCocoa.mm:2306,2334`, confirming this is the general-purpose permission-change
notification path, not something special-cased for the `permissions` API alone.)

### Firing in content scripts

Resolved by necessity from section 2's findings, not by separate source reading: section 2
establishes, per engine and with its own citations, that a content script cannot reach the
`permissions` namespace at all in Chrome (feature `contexts` restriction) or WebKit (`MainWorldOnly`
interface attribute, false for an isolated content-script world), and cannot reach anything on the
namespace except `request()` in Firefox (`allowedContexts` override on `request` alone; `getAll`,
`contains`, `remove`, `onAdded`, `onRemoved` fall back to the namespace default, which excludes
content scripts). A JavaScript property that is unreachable from a given context cannot have a
listener attached to it from that context; this holds independent of anything else about event
delivery, since there is no `permissions.onAdded`/`onRemoved` object present in a content script's
global for `addListener` to be called on in the first place, in any of the three engines. No
special-case event-delivery mechanism that could bypass this was found in any of the three engines'
source read for this task.

## 6. `data_collection`

See section 3. Firefox-only, pref-gated (`extensions.dataCollectionPermissions.enabled`,
default `false`), appears as an optional third array (`OptionalDataCollectionPermission[]`) on
both the `Permissions` dictionary passed to `request`/`remove`/events and the `AnyPermissions`
dictionary returned by `getAll`/`contains`. Confirmed absent from Chrome's schema and WebKit's
IDL dictionary.

## 7. Recognized permission name set

Computed 2026-09-03 against three local checkouts (`~/chromium/src`, `~/firefox`, `~/WebKit`),
read-only, filtered by real reachability rather than mere presence in a feature table (an
allowlisted or component-only entry does not count). Full method and per-engine source citations
are in the standalone research note this section summarizes.

Per-engine recognized counts: Chrome 86, Firefox 51, Safari 17. Safari has zero names the other
two lack.

The three-way intersection, all sixteen recognized by all three engines:

```
activeTab, alarms, clipboardWrite, contextMenus, cookies, declarativeNetRequest,
declarativeNetRequestFeedback, declarativeNetRequestWithHostAccess, nativeMessaging,
notifications, scripting, storage, tabs, unlimitedStorage, webNavigation, webRequest
```

Two semantic divergences beyond mere presence/absence, both source-verified:

- **`menus` vs `contextMenus`**: Firefox and Safari treat `menus` and `contextMenus` as two
  spellings of the same permission (Firefox: `browser/components/extensions/schemas/menus.json`,
  one block listing both strings; Safari: `WebExtension.cpp`'s `supportedPermissions()` lists
  both `menus()` and `contextMenus()`). Chrome has no `menus` entry at all, only `contextMenus`.
  This is why `contextMenus` makes the sixteen-name intersection while `menus` falls one engine
  short (Firefox + Safari only).
- **`webRequestBlocking`**: present in all three engines' permission tables, but Chrome only
  grants it to an ordinary extension under Manifest V2; a Manifest V3 extension can only obtain
  it through enterprise policy (`extensions/common/api/_permission_features.json`, two
  alternatives gated by `max_manifest_version`/`min_manifest_version`). Firefox and Safari carry
  no such manifest-version split and grant it uniformly whenever declared. The permission name
  itself is recognized identically everywhere; what declaring it gets you is not.

This set is not stable: see `divergences.md` for the three Safari permission names sitting
behind a currently-disabled build flag, any one of which would change the intersection with no
spec change required.

## Resolved in a later pass (previously undetermined)

- The uncited trailing-callback claim (section 1a): resolved for all three browsers, all four
  methods, uniform across manifest versions.
- Firefox's `requireUserInput: true` enforcement mechanism (section 2, "User gesture"): resolved,
  with a genuine caveat for MV3 background-service-worker callers (open Firefox bug 1728328).
- Chrome's `GetNativeWindowForUI()` semantics for a background service worker (section 2, "Active
  window requirement"): resolved.
- Whether WebKit enforces a managed/MDM-style block on `permissions.request()` (section 2,
  "Enterprise/managed policy blocking"): classified not in open source, on a broadened search.
- Whether Firefox's/WebKit's user-facing permission-management UI, and policy-driven changes,
  fire `onAdded`/`onRemoved` (section 5): resolved for both engines and both triggers.
- Content-script reachability of `onAdded`/`onRemoved` (section 5): confirmed as a necessary
  consequence of already-cited facts, not a separate open question.
- Origin path-stripping in `origins` entries (section 3): resolved for Firefox (yes, at storage
  time); WebKit's parse-time behavior confirmed (no stripping), its match-time consequence left
  unchecked as a bounded, explicitly-scoped gap.

## Undetermined / not independently confirmed in this pass

No items remain in this category for this document as of the most recent pass; see "Resolved in
a later pass" above for what was previously listed here.

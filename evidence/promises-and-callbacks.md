# Promises and callbacks: three-way source validation

Read only, no builds, against the Chromium, WebKit and Gecko source trees as checked out on
2026-09-03. Every claim below cites the file and line read.

This topic was already partly validated for one concrete API in
`evidence/permissions-api.md` section 1a ("Trailing callback argument on every method"), which
established that Chrome, Firefox and Safari all accept an optional trailing callback on
`permissions.getAll()`, `contains()`, `request()`, and `remove()`, uniformly across Manifest V2
and Manifest V3. This file generalizes that finding: it traces the mechanism each engine uses to
realize the dual signature to its generic, schema/attribute-driven form (not specific to
`permissions`), and researches error propagation, result shape, and genuine exceptions to the
general rule, none of which section 1a covered.

## 0. Source files read

Chromium:
- `extensions/renderer/bindings/api_signature.cc` (`BuildReturnsAsyncFromValues`,
  `ArgumentParser::ParseCallback`)
- `extensions/renderer/bindings/api_request_handler.cc`
  (`AsyncResultHandler::ResolveRequest`/`ResolvePromise`/`CallExtensionCallback`,
  `APIRequestHandler::GetAsyncResultHandler`, `APIRequestHandler::CompleteRequestImpl`)
- `extensions/renderer/bindings/api_last_error.cc`, `api_last_error.h`
  (`APILastError::ClearError`/`ReportUncheckedError`)
- `extensions/renderer/bindings/api_binding_js_util.cc` (`SetLastError`, `ClearLastError`,
  `HasLastError`, `GetLastErrorMessage`, `RunCallbackWithLastError`; a JS-facing surface used by
  a handful of hand-written custom bindings, cited to show the same lastError primitive is
  reused there, not that it is the generic dispatch path)
- `chrome/common/extensions/api/permissions.json` (concrete instance, already covered in
  `evidence/permissions-api.md`)
- `chrome/common/extensions/api/desktop_capture.json`, `chrome/common/extensions/api/
  context_menus.json`, `extensions/common/api/events.json` (methods marked
  `does_not_support_promises`)

Gecko:
- `toolkit/components/extensions/Schemas.sys.mjs` (`FunctionType.parseSchema`,
  `FunctionEntry.getDescriptor`)
- `toolkit/components/extensions/ExtensionCommon.sys.mjs`
  (`LocalAPIImplementation.callAsyncFunction`, `Context.wrapPromise`, `Context.withLastError`)
- `toolkit/components/extensions/schemas/permissions.json` (concrete instance, already covered
  in `evidence/permissions-api.md`)
- `toolkit/components/extensions/schemas/browser_action.json`,
  `toolkit/components/extensions/schemas/clipboard.json`,
  `toolkit/components/extensions/schemas/content_scripts.json`,
  `toolkit/components/extensions/schemas/captive_portal.json` (methods declared `"async": true`
  rather than `"async": "callback"`)
- `toolkit/components/extensions/ExtensionChild.sys.mjs`,
  `browser/components/extensions/parent/ext-devtools-inspectedWindow.js` (`SpreadArgs` usage)

WebKit:
- `Source/WebKit/WebProcess/Extensions/Bindings/Scripts/CodeGeneratorExtensions.pm`
  (`ReturnsPromiseWhenCallbackIsOmitted`/`CallbackHandler` codegen, around
  `$returnsPromise`/`$callbackHandlerArgument`)
- `Source/WebKit/WebProcess/Extensions/Bindings/JSWebExtensionWrapper.h`,
  `JSWebExtensionWrapper.cpp` (`WebExtensionCallbackHandler`: `create`, `reportError`, `call`)
- `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm`
  (`WebExtensionAPIRuntimeBase::reportError`, `WebExtensionAPIRuntime::lastError`)
- `Source/WebKit/WebProcess/Extensions/Interfaces/*.idl` (all 37 API interfaces, to check which
  carry `ReturnsPromiseWhenCallbackIsOmitted`)
- `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl` (concrete
  instance, already covered in `evidence/permissions-api.md`)
- `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIDevToolsInspectedWindowCocoa.mm`
  (multi-value callback example)

## 1. The general rule is schema/attribute-driven, not method-by-method, in all three engines

This confirms and generalizes `evidence/permissions-api.md` section 1a: the dual signature is not
special-cased per method anywhere in any of the three engines. Each realizes it once, generically,
from a per-function (Chrome, Firefox) or per-interface (Safari) declaration, at bind/codegen time.

- **Chrome**: `BuildReturnsAsyncFromValues()` reads a `returns_async` schema entry and sets
  `promise_support` to `kUnsupported` only if the entry has a `does_not_support_promises` key,
  otherwise `kSupported` and the callback `optional` (`extensions/renderer/bindings/
  api_signature.cc:41-56`). At call time, `ArgumentParser::ParseCallback()` looks at the actual
  last argument: if omitted and `promise_support_ == kSupported`, `async_type_ = kPromise`; if a
  function was passed, `async_type_ = kCallback` regardless of promise support
  (`api_signature.cc:364-395`). `APIRequestHandler::GetAsyncResultHandler()` only allocates a
  `v8::Promise::Resolver` (and so only produces a promise to return) when `async_type ==
  kPromise`, with an explicit comment that a promise-based request "should never be started with
  a callback being passed in" (`extensions/renderer/bindings/api_request_handler.cc:577-600`).
  None of this code is specific to `permissions`; it runs for every schema-declared function with
  a `returns_async` entry.
- **Firefox**: `FunctionType.parseSchema()` computes `hasAsyncCallback` generically from whether
  the schema's `async` value names the last declared parameter
  (`toolkit/components/extensions/Schemas.sys.mjs:2651-2677`). The generated call stub
  (`FunctionEntry.getDescriptor()`) pops the real last call argument as `callback` only if
  `hasAsyncCallback`, then always calls `apiImpl.callAsyncFunction(actuals, callback, ...)`
  (`Schemas.sys.mjs:3067-3095`). `LocalAPIImplementation.callAsyncFunction()` in turn calls
  `this.context.wrapPromise(promise, callback)` unconditionally
  (`toolkit/components/extensions/ExtensionCommon.sys.mjs:1143-1157`); `wrapPromise()` is the
  single generic dispatch point, documented in its own comment as returning "a promise object...
  Otherwise, undefined" depending only on whether `callback` is non-null
  (`ExtensionCommon.sys.mjs:869-872`). Again, none of this is specific to any one namespace.
- **Safari**: `ReturnsPromiseWhenCallbackIsOmitted` is an IDL extended attribute, declared once
  per interface (or, in `WebExtensionAPIMenus.idl`, repeated per method, but present on every
  method there that takes a callback) rather than duplicated as custom logic per method.
  `CodeGeneratorExtensions.pm` resolves it per function as `$function->extendedAttributes->
  {"ReturnsPromiseWhenCallbackIsOmitted"} || $interface->extendedAttributes->
  {"ReturnsPromiseWhenCallbackIsOmitted"}` (line 521), and the generated body is templated once:
  when the attribute is set and the JS caller omitted the callback, it fabricates a deferred
  promise and wraps its resolve/reject functions in the same `WebExtensionCallbackHandler` type
  used for a real callback (`toJSPromiseCallbackHandler`, lines 729-742 in
  `CodeGeneratorExtensions.pm`); when the attribute is not set (or a callback was actually
  supplied), the real callback (or, if none, an error-reporting stand-in,
  `toJSErrorCallbackHandler`, lines 744-751) is used instead. This template is shared by every
  method with a `[Optional, CallbackHandler]` parameter across the 32 interface files that carry
  the attribute (grep confirms 32 of the 37 `.idl` files under
  `Source/WebKit/WebProcess/Extensions/Interfaces/`; the other 5 are `WebExtensionAPIEvent.idl`,
  `WebExtensionAPIPort.idl`, `WebExtensionAPIWebNavigationEvent.idl`,
  `WebExtensionAPIWebRequestEvent.idl`, `WebExtensionAPIWindowsEvent.idl`: all event-listener or
  message-port interfaces whose methods are `addListener`/`removeListener`/`postMessage`, not
  asynchronous result-bearing methods, so they are not instances of this rule one way or the
  other).

No manifest-version conditioning was found anywhere in this machinery in any of the three
engines: `grep -n "ManifestVersion\|manifestVersion"` against `CodeGeneratorExtensions.pm`
returns nothing, and the Chrome/Firefox files above were already checked for this in
`evidence/permissions-api.md` section 1a (no `manifest_version` branch in `api_signature.cc`,
`Schemas.sys.mjs`, or `ExtensionCommon.sys.mjs`'s async dispatch path). The dual signature, where
it exists at all for a method, is uniform across Manifest V2 and Manifest V3 in all three
engines.

## 2. What the method call itself returns

- **Chrome**: `GetAsyncResultHandler()` only constructs a `v8::Promise::Resolver`, and so only
  returns a promise to the caller, `if (async_type == binding::AsyncResponseType::kPromise)`
  (`api_request_handler.cc:588-596`); the `else if` branch that runs when a callback was supplied
  builds no resolver and produces no promise (`api_request_handler.cc:597-602`). The bound JS
  function itself has no other return path, so a callback-form call returns `undefined`.
- **Firefox**: `wrapPromise(promise, callback)`'s own doc comment states the return value
  directly: "If callback is null, a promise object belonging to the target scope. Otherwise,
  undefined." (`ExtensionCommon.sys.mjs:870-872`), and the `if (callback) { ... } else { return
  new this.Promise(...) }` structure implements exactly that (`ExtensionCommon.sys.mjs:881-936`):
  the callback branch has no `return` statement affecting the caller's value, so the call
  evaluates to `undefined`.
- **Safari**: the generated function's return expression is `promiseResult ?: $defaultReturnValue`
  (`CodeGeneratorExtensions.pm:730`), and `promiseResult` is only assigned inside `if (!
  ${callbackHandlerArgument})` (line 736), i.e. only when no callback was supplied. When a
  callback is supplied, `promiseResult` stays null and the function returns
  `$defaultReturnValue`, which `die "Returning a Promise is only allowed for void functions"`
  (line 731) guarantees is the void function's ordinary default: `undefined`.

All three: `undefined` when a callback is supplied, a promise when it is omitted. No engine
returns both.

## 3. Error propagation: promise rejection, or `runtime.lastError` plus the same callback call

This is the question flagged in the brief as the likely most interesting divergence. It turned
out to be the opposite: all three converge, including on the “unchecked error” warning.

- **Chrome**: `AsyncResultHandler::ResolveRequest()` sets `runtime.lastError`
  (`last_error->SetError(context, error)`) only `if (set_last_error)`, where `set_last_error =
  promise_resolver_.IsEmpty() && !error.empty()`: i.e. only for a callback-based request that
  failed, never for a promise-based one (`api_request_handler.cc:217-222`). It then dispatches to
  `ResolvePromise()`, which calls `resolver->Reject(context, v8_error)` on a non-empty error
  (`api_request_handler.cc:300-306`), or to `CallExtensionCallback()`, which invokes the
  extension's callback with the ordinary result `args` regardless of whether `error` was set ,
  the error is never passed to the callback as an argument (`api_request_handler.cc:254-262,
  309-320`). After the callback returns, `last_error->ClearError(context, true)` is called with
  `report_if_unchecked = true` (`api_request_handler.cc:266-268`); if a request completes with an
  error but has no async handler at all, the error is reported directly `as if it were unchecked`
  (`api_request_handler.cc:623-629`). `APILastError`'s unchecked-error message is literally
  prefixed `"Unchecked runtime.lastError: "` (`extensions/renderer/bindings/
  api_last_error.cc:24`).
- **Firefox**: `wrapPromise()`'s callback branch, on rejection, calls `this.withLastError(error,
  caller, () => { ... this.applySafeWithoutClone(callback, [], caller) })`
  (`ExtensionCommon.sys.mjs:899-914`): the callback is invoked with zero arguments (no error
  argument), while `withLastError()` sets `this.lastError = this.normalizeError(error)` before
  calling it and, in a `finally` block, does `if (!this.checkedLastError) { Cu.reportError(
  \`Unchecked lastError value: ${this.lastError}\`, caller) }`
  (`ExtensionCommon.sys.mjs:828-836`). The promise branch, on rejection, instead calls `reject`
  directly with the error value (`ExtensionCommon.sys.mjs:943` onward, mirroring the resolve path
  already quoted in section 2 above): no `lastError` involvement for the promise form.
- **Safari**: `WebExtensionCallbackHandler::reportError()` branches on which kind of handler it
  is: if it wraps a real runtime (`m_runtime` set, i.e. the callback form), it delegates to
  `runtime->reportError(message, *this)`, which sets `m_lastError`, invokes the wrapped callback
  through the handler (`handler()`, itself `callback.call()`), and afterward checks
  `m_lastErrorAccessed`, logging `"Unchecked runtime.lastError: " + errorMessage` to
  `console.error` if the callback never read `runtime.lastError`
  (`Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:97-127`,
  message text built at line 111). If instead the handler wraps a promise (`m_rejectFunction`
  set, i.e. the promise form), `reportError()` skips the runtime path entirely and calls the
  reject function directly with a JS `Error` object
  (`Source/WebKit/WebProcess/Extensions/Bindings/JSWebExtensionWrapper.cpp:134-152`). The
  property itself is exposed as `runtime.lastError`
  (`Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIRuntime.idl:72`,
  `WebExtensionAPIRuntimeCocoa.mm:314-320`).

All three: the promise form rejects with the error, carrying no `lastError` involvement. The
callback form invokes the callback exactly as it would on success (no error argument added), sets
`runtime.lastError` for the duration of that one invocation, clears it afterward, and logs an
"unchecked lastError" warning if the callback never read it. The property name (`runtime.
lastError`), the mechanism (set around the callback call, not passed as an argument), and the
unchecked-access warning all agree across Chrome, Firefox and Safari.

## 4. Result value: same shape in both forms, with one sourced exception in Firefox

- **Chrome**: `ResolveRequest()` builds one `args` vector and passes it to both `ResolvePromise()`
  and `CallExtensionCallback()` unchanged (`api_request_handler.cc:229-233, 254-261`).
  `ResolvePromise()` asserts `response_args.size() <= 1`
  (`api_request_handler.cc:277`) and resolves with `response_args[0]` or `undefined` if empty
  (`api_request_handler.cc:284-291`); the callback receives that same `args` vector as its
  argument list (`api_request_handler.cc:260-261, 310-320`). A method whose native result would
  need more than one callback argument is not given `returns_async` promise support at all (see
  section 5): Chrome has no dual-form method observed where the two forms disagree on shape.
- **Safari**: the generated success path calls the same `WebExtensionCallbackHandler::call()`
  family (0-, 1-, 2-, or 3-argument overloads,
  `Source/WebKit/WebProcess/Extensions/Bindings/JSWebExtensionWrapper.cpp:156-181`) regardless of
  whether the handler wraps a real callback or a promise's resolve function: the same call site
  in each API's generated/hand-written implementation drives both. Every multi-argument `call()`
  usage found (for example `devtools.inspectedWindow.eval()`,
  `Source/WebKit/WebProcess/Extensions/API/Cocoa/
  WebExtensionAPIDevToolsInspectedWindowCocoa.mm:87,94`) packs its values into a single JS array
  first and calls the one-argument `call()` overload with that array, so the promise and the
  callback are actually given the same single array value in every case examined; no case of
  Safari's `call(argumentOne, argumentTwo)`/`call(argumentOne, argumentTwo, argumentThree)`
  overloads being reached from a `ReturnsPromiseWhenCallbackIsOmitted` method was found in the
  files read.
- **Firefox**: `wrapPromise()` handles a `SpreadArgs` result specially, and the two forms
  disagree on shape for it. On success, the callback branch does `applySafe(callback, args,
  caller)` where `args` is the `SpreadArgs` array, invoked so each element becomes a separate
  positional argument (`ExtensionCommon.sys.mjs:893-894`); the promise branch instead does
  `applySafe(resolve, value.length == 1 ? value : [value], caller)`
  (`ExtensionCommon.sys.mjs:936-937`): for a `SpreadArgs` of length other than 1, this resolves
  the promise with the array itself as a single value, not spread. A real method uses this:
  `devtools.inspectedWindow.eval()` returns `new SpreadArgs([evalResult.value,
  evalResult.exceptionInfo])` (`browser/components/extensions/parent/
  ext-devtools-inspectedWindow.js:35`), so its callback is invoked as `(result, exceptionInfo) =>
  {}` (two positional arguments) while its promise resolves to the single array `[result,
  exceptionInfo]`. `SpreadArgs`/`NoCloneSpreadArgs` construction was also found in
  `ExtensionChild.sys.mjs` and `browser/components/extensions/parent/ext-devtools-network.js`,
  so this is not a one-off.

Conclusion: in every case found in Chrome and Safari, the callback receives the same value the
promise resolves with, in the same shape. Firefox has a real, sourced exception: at least one
method (and the `SpreadArgs` mechanism generally, used by more than one namespace) gives the
callback form multiple positional arguments while the promise form receives a single bundled
array value for the same result.

## 5. Methods that support only one form

Not every asynchronous method supports both. The two browsers with exceptions diverge in which
direction they break the rule; no exception was found in Safari.

- **Chrome, callback-only**: `desktopCapture.chooseDesktopMedia()` is marked
  `"does_not_support_promises": "Synchronous return and callback crbug.com/40154924, Multi-
  parameter callback crbug.com/40221043"` (`chrome/common/extensions/api/
  desktop_capture.json:37,103`); it already has a synchronous `"returns"` value (an integer
  request id used to cancel the prompt) in addition to its callback
  (`desktop_capture.json:104-107`), and its callback itself takes two parameters
  (`desktop_capture.json:84-99`), neither of which fits the single-value promise-resolution shape
  used elsewhere in Chrome (section 4). `contextMenus.create()` is the same shape of exception:
  `"does_not_support_promises": "Synchronous return and callback crbug.com/40154924"`
  (`chrome/common/extensions/api/context_menus.json:206`), alongside its own synchronous
  `"returns"` value, the created item's id (`context_menus.json:180-184`). `contextMenus.update()`,
  `.remove()`, and `.removeAll()`, which have no synchronous return value, carry no such flag and
  support both forms normally. A third, differently-caused bucket exists in
  `extensions/common/api/events.json`: the declarative `Event.addRules()`-style methods used by
  `declarativeContent`/`declarativeWebRequest`-style APIs are flagged
  `"does_not_support_promises": "Related custom hooks do not handle promises crbug.com/1520656"`
  (`events.json:140,179,212`): an implementation gap tracked in that bug, not a synchronous-
  return conflict.
- **Firefox, promise-only**: a schema function is declared `"async": true` rather than `"async":
  "callback"` when it has no parameter whose name matches a callback name; `Schemas.sys.mjs`'s
  `hasAsyncCallback` is then `false` (`Schemas.sys.mjs:2672-2677`), so the generated stub never
  pops a trailing callback argument off the call, and the method is reachable only through the
  promise it always returns. This is not a rare case: `"async": true` occurs 99 times against 196
  occurrences of `"async": "callback"` across `toolkit/components/extensions/schemas/*.json` and
  `browser/components/extensions/schemas/*.json` (plus 3 of `"async": "responseCallback"`, the
  same mechanism under a different callback-parameter name). Concrete examples read directly:
  `browserAction.openPopup()` (`toolkit/components/extensions/schemas/
  browser_action.json:491-494`), `browserAction.isEnabled()`, `browserAction.
  getBadgeTextColor()`/`setBadgeTextColor()` (same file), `clipboard.setImageData()`
  (`toolkit/components/extensions/schemas/clipboard.json`), `contentScripts.register()`/
  `.unregister()` (`toolkit/components/extensions/schemas/content_scripts.json`), and
  `captivePortal.getState()`/`.getLastChecked()`
  (`toolkit/components/extensions/schemas/captive_portal.json`). `permissions`'s own four methods
  are all `"async": "callback"` (already cited in `evidence/permissions-api.md`), so this
  divergence would not have been visible from `permissions` alone.
- **Safari**: section 1 above already establishes that every one of the 32 interface files with a
  genuine asynchronous, callback-accepting method carries
  `ReturnsPromiseWhenCallbackIsOmitted`, covering every `[Optional, CallbackHandler] function
  callback` parameter found across those files. No interface or method was found in the 37 `.idl`
  files under `Source/WebKit/WebProcess/Extensions/Interfaces/` that accepts a callback for an
  asynchronous result without also supporting the promise form. Absence of a counterexample in
  this tree is not proof none exists, but the same systematic per-interface grep used for the
  32/37 count above was run for exactly this.

## 6. Manifest V2 vs Manifest V3

No divergence found anywhere in this document's research beyond what section 1 already reports:
none of the three engines' generic dual-signature machinery branches on manifest version, and
none of the exceptions in section 5 are manifest-version-scoped either: `desktop_capture.json`,
`context_menus.json`, and `events.json`'s `does_not_support_promises` entries carry no
`min_manifest_version`/`max_manifest_version` restricting them to one version, and Firefox's
`"async": true` declarations are a property of the function's schema entry, unconditioned on
manifest version by anything in `Schemas.sys.mjs`.

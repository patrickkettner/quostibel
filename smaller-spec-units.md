# Sub-namespace spec units: candidates for index.bs

Survey only. No spec text drafted. Source trees read-only: Chromium, Gecko, WebKit.
No edits, no builds, nothing filed or cloned.

Two entries (Permissions dictionary, `runtime.id`) reuse prior source-confirmed
findings from `evidence/permissions-api.md` and `evidence/extension-ids.md`
rather than redoing that work. Everything else below is new for this pass,
found by mining `webext-meta-types`'s `coverage.json` and `dist/metadata.json`
for three-way "no divergence note" members, then confirmed (or rejected)
against real engine source.

## Ranked table

| # | Unit | Category | Est. lines | Engine agreement | Evidence | Target heading |
|---|---|---|---:|---|---|---|
| 1 | `storage.StorageChange` dict + `storage.onChanged` event | small dict + single event | ~15 | three-way, clean | source-confirmed | new `# Storage` (StorageChange + onChanged) |
| 2 | `tabs.onRemoved` event | single event | ~10 | three-way, clean | source-confirmed | new, alongside a future `tabs` treatment |
| 3 | Permissions dictionary (`{permissions?, origins?}`) | small dict | ~10 | three-way, Firefox narrows element types + adds `data_collection` | source-confirmed (row 3, reused) | `# Host permissions` or new `permissions` section |
| 4 | `alarms.Alarm` dict | small dict | ~12 | three-way for `name`/`scheduledTime`/`periodInMinutes`; `persistAcrossSessions` is Chrome-only | source-confirmed | new, alongside a future `alarms` treatment |
| 5 | `commands.Command` dict | small dict | ~10 | three-way for field set; WebKit's required/optional split not confirmed | source-confirmed field set, optionality declaration-only for WebKit | new, alongside a future `commands` treatment |
| 6 | `runtime.onStartup` event | single event | ~5 | three-way, clean, zero-argument | source-confirmed | new, small addition near `# Concepts` |
| 7 | `runtime.getURL(path): string` | single method | ~8 | three-way signature match; resolution algorithm confirmed in WebKit only | signature source-confirmed all three; behavior source-confirmed WebKit only | ties into extension origin / row 6 |
| 8 | `runtime.id` getter | single method (getter) | ~5 | three-way, same property name and return type; underlying ID semantics diverge (see row 6) | source-confirmed (row 6, reused) | `# Concepts` > Uniqueness of extension IDs |
| 9 | Manifest key `description` | manifest key | ~5 | three-way: optional, localizable string; localization *mechanism* differs (Chrome/Firefox allowlist vs. WebKit whole-manifest pass) | source-confirmed shape, mechanism divergence noted | `### Key description` (currently "This key may be present.") |

Rejected or not pursued, with reasons:

- **`tabs.TabStatus`, `windows.WindowState`, `windows.WindowType` enums**: `webext-meta-types/dist/metadata.json` flags all three "union of divergent
  definitions." Each engine's member set genuinely differs (e.g. `WindowState`:
  Chrome alone has `locked-fullscreen`, Firefox alone has `docked`). Not
  cross-engine identical; excluded rather than forced into a shared core.
- **`cookies.CookieStore`**: only `id`/`tabIds` are three-way; `incognito` is
  Firefox+Safari only, absent from Chrome per `metadata.json`. Not deep-dived
  against source this pass; declaration-only, lower tier.
- **`runtime.PlatformInfo`**: `metadata.json` flags both `arch` and `os`
  "shape differs between browsers." Each engine has its own OS/arch string
  enum. Not deep-dived; declaration-only, lower tier.
- **Manifest keys `icons`, `options_ui`, `content_security_policy`**: named in
  the task brief as candidates but not investigated this pass. Not determined,
  not guessed.

---

## 1. `storage.StorageChange` + `storage.onChanged`

**Why it ranks first**: the cleanest three-way match found in this pass. No
per-field divergence in the dictionary; the event signature is byte-identical
in argument shape across all three engines, confirmed against the actual
dispatch call, not just a schema.

**`StorageChange` dictionary**: `{ oldValue?: any; newValue?: any }` in all
three:

- Chromium: `extensions/common/api/storage.json:19-32`
- Firefox: `toolkit/components/extensions/schemas/storage.json:9-23`
- WebKit: `dictionary WebExtensionStorageChange { any oldValue; any newValue; };`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIStorageArea.idl:34-37`

**`onChanged(changes, areaName)` event**:

- Chromium: `extensions/common/api/storage.json:217-233`: `changes: object<StorageChange>`, `areaName: string`
- Firefox: `toolkit/components/extensions/schemas/storage.json:191-207`: identical text
- WebKit: declared `readonly attribute WebExtensionAPIEvent onChanged;` on
  `WebExtensionAPIStorage.idl:33`, and the actual two-argument dispatch is in
  the implementation, not just the IDL:
  `namespaceObject.storage().onChanged().invokeListenersWithArgument(changes, areaName.get());`: `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIStorageCocoa.mm:118`.
  The `changes` NSDictionary is built key-by-key as `{oldValue?, newValue?}`
  pairs in `Source/WebKit/UIProcess/Extensions/API/WebExtensionContextAPIStorage.cpp:228-259`.

**One divergence worth noting in the section**: Chrome and Firefox's schema
text lists `"managed"` as a fourth possible `areaName` value alongside
`local`/`sync`/`session` (`storage.json:224` Chromium, `:205` Firefox); WebKit
only implements `local`/`sync`/`session` (`WebExtensionAPIStorage.idl:30-32`).
This doesn't affect the dict or the event's shape, only the domain of
`areaName` strings.

**Caveat from prior work applies here**: `storage` was previously flagged as
outside Safari's `READ_NAMESPACES` set in `safari-webextension-types`
(`specability-analysis.md` section 4), meaning the *npm-package-derived*
Safari types for `storage` weren't source-verified before. This pass closes
that gap directly against WebKit source rather than through the generated
types.

## 2. `tabs.onRemoved`

**`onRemoved(tabId: integer, removeInfo: {windowId: integer, isWindowClosing: boolean})`**:

- Chromium: `chrome/common/extensions/api/tabs.json:1442-1455`
- Firefox: `browser/components/extensions/schemas/tabs.json:1937-1957` (verbatim
  match, differs only in `isWindowClosing` description wording)
- WebKit: `readonly attribute WebExtensionAPIEvent onRemoved;`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPITabs.idl:132`.
  Actual dispatch, confirming both the argument count and the `removeInfo`
  field names:
  ```
  auto *removeInfo = @{ windowIdKey: @(toWebAPI(windowIdentifier)), isWindowClosingKey: @(windowIsClosing == WebExtensionContext::WindowIsClosing::Yes) };
  namespaceObject.tabs().onRemoved().invokeListenersWithArgument(@(toWebAPI(tabIdentifier)), removeInfo);
  ```: `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPITabsCocoa.mm:1328-1337`.

No divergence found. This is a full-namespace-free unit: a `RemoveInfo`
informal dict plus one event, specifiable without any other part of `tabs`.

## 3. Permissions dictionary

Reused from `evidence/permissions-api.md`, not redone here.
`{ permissions?: string[]; origins?: string[] }` holds in all three; Firefox
narrows the element types to its own manifest-key enums and adds an optional
`data_collection` field the other two engines lack. Citations:
`dist/chrome-only.d.ts:9358-9435` (types), and per that row's file:line
citations into `chrome/common/extensions/api/permissions.json`,
`toolkit/components/extensions/schemas/permissions.json`, and
`Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIPermissions.idl:26-29`.

## 4. `alarms.Alarm` dictionary

**Core three fields, identical in all three**: `name: string` (required),
`scheduledTime: number` (required), `periodInMinutes?: number` (optional).

- Chromium (current, WebIDL): `extensions/common/api/alarms.webidl:5-19`: `required DOMString name; required double scheduledTime; double
  periodInMinutes;` (no `required` keyword on this one = optional in WebIDL).
  Chrome's dictionary *also* declares `required boolean
  persistAcrossSessions;` with a comment acknowledging the cross-browser gap:
  "you should set this explicitly to maximize compatibility across browsers."
- Firefox: `toolkit/components/extensions/schemas/alarms.json:7-24`: `name`
  and `scheduledTime` have no `"optional": true` (required), `periodInMinutes`
  does (optional). No `persistAcrossSessions` field at all.
- WebKit: `dictionary WebExtensionAlarm { DOMString name; double
  scheduledTime; double periodInMinutes; };`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIAlarms.idl:26-30`.
  Confirmed against the actual serializer, not just the IDL:
  `name` and `scheduledTime` are set unconditionally, `periodInMinutes` only
  `if (alarm.repeatInterval)`: i.e. genuinely optional: `Source/WebKit/WebProcess/Extensions/API/WebExtensionAPIAlarms.cpp:47-57`.
  No `persistAcrossSessions` field anywhere in WebKit's alarm code.

**Note**: this contradicts what `webext-meta-types/dist/index.d.ts` currently
says about this interface (it marks `name`/`scheduledTime` as "optional in
Safari, required in Chrome, Firefox" and `persistAcrossSessions` as
Chrome-only-optional): the current npm-package-derived Safari type doesn't
match what WebKit source actually does for `periodInMinutes`'s optionality
pattern; source is the deciding evidence here, not the declaration file.

## 5. `commands.Command` dictionary

`{ name?: string; description?: string; shortcut?: string }`:

- Chromium: `chrome/common/extensions/api/commands.json:14-31`, all three
  `"optional": true`
- Firefox: `browser/components/extensions/schemas/commands.json:77-95`,
  verbatim match to Chromium's schema
- WebKit: `dictionary WebExtensionCommand { DOMString description; DOMString
  name; DOMString shortcut; };`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPICommands.idl:26-30`

**Gap**: WebKit's custom IDL dialect marks optionality on function parameters
with `[Optional]` but has no such annotation for dictionary members anywhere
in this file, so whether WebKit's runtime treats these three fields as
optional (matching Chrome/Firefox) or always-populated could not be confirmed
from the IDL alone in this pass, and the `.mm` serializer for `Command`
specifically (as opposed to `WebExtensionCommandParameters`, its internal
struct with a different field named `identifier` instead of `name`) was not
traced. Field set and names are source-confirmed; optionality is not.

## 6. `runtime.onStartup`

Zero-argument event, fired once per browser/profile startup (not fired for
incognito/private profiles in any of the three):

- Chromium: `extensions/common/api/runtime.json:663-666`: no `parameters` key
- Firefox: `toolkit/components/extensions/schemas/runtime.json:696-699`: no
  `parameters` key
- WebKit: `[MainWorldOnly] readonly attribute WebExtensionAPIEvent onStartup;`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIRuntime.idl:85`.
  Dispatch confirmed as zero-argument:
  `namespaceObject.runtime().onStartup().invokeListeners();`: `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:856`.

Smallest possible unit in this list: essentially one sentence plus "no
parameters." Ranked below the dictionaries above only because it carries no
dependency weight (nothing else in index.bs references it yet) and is almost
too small to need its own heading rather than a line inside a future
`runtime` section.

## 7. `runtime.getURL(path: string): string`

Signature match:

- Chromium: `extensions/common/api/runtime.json:376-390`
- Firefox: `toolkit/components/extensions/schemas/runtime.json:386-399`
- WebKit: `[URL, ConvertNullStringTo=Null, RaisesException] DOMString
  getURL(DOMString resourcePath);`: `Source/WebKit/WebProcess/Extensions/Interfaces/WebExtensionAPIRuntime.idl:58`

Behavior, WebKit only: `return URL { extensionContext().baseURL(),
resourcePath }.createNSURL().autorelease();`: `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:166-171`: i.e. resolve `path` against the extension's own origin, the same mechanism
already established for extension origins in row 6. Chrome's and Firefox's
equivalent resolution code (their JS/C++ bindings layer, not the schema text)
was not traced this pass: the schema only says "converts a relative path...
to a fully-qualified URL," which is consistent with but not proof of the same
algorithm. Report the signature as source-confirmed three-way and the
resolution algorithm as WebKit-confirmed, Chrome/Firefox not determined.

## 8. `runtime.id`

Reused from `evidence/extension-ids.md`. Same property name
and return type (`string`) in all three:

- Chromium: `chrome.runtime.id`, schema at `extensions/common/api/runtime.json:312-314`
- Firefox: `browser.runtime.id` returns `extension.id`: `toolkit/components/extensions/child/ext-runtime.js:133`
- WebKit: `browser.runtime.id` returns `uniqueIdentifier()`: `Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:186-190`

The getter itself is identical; what the returned string *means* (how it's
derived, whether it's stable, whether it's guessable from a web page) differs
fundamentally by design across the three engines: that's the subject of row
6's "Uniqueness of extension IDs" findings, not new ground. Listed here as a
one-line addendum a spec author could attach to that existing section, not as
independent drafting work.

## 9. Manifest key `description`

Optional, localizable string, in all three:

- Chromium: parsed by `DescriptionHandler::Parse`: must be a string if
  present, stored only if non-empty: `extensions/common/manifest_handlers/description_info.cc:31-46`. Localized
  via a fixed per-key allowlist that explicitly includes `description`: `extensions/common/extension_l10n_util.cc:253`.
- Firefox: `{ "type": "string", "optional": true, "preprocess": "localize" }`: `toolkit/components/extensions/schemas/manifest.json:42-45`
- WebKit: `m_displayDescription = manifestObject->getString(descriptionManifestKey);`: `Source/WebKit/UIProcess/Extensions/WebExtension.cpp:958`: read from a
  manifest object that has already been run through a *generic* whole-manifest
  localization pass (`localizedManifestObject =
  localization->localizedJSONforJSON(manifestObject);`: `WebExtension.cpp:322`), rather than a per-key allowlist.

Shape (optional string) and end-user-visible behavior (supports `__MSG_x__`
substitution) are the same in all three. The localization *mechanism* is
structurally different: Chrome and Firefox apply substitution to a fixed list
of known-localizable keys; WebKit substitutes across the entire manifest
object generically. Worth naming as an implementation-note, not a blocker: index.bs's current text for this key is only "This key may be present."

---

## Source-confirmed vs. declaration-only summary

**Source-confirmed (implementation code read, not just schema/IDL declaration)**:
storage.StorageChange + storage.onChanged (all three), tabs.onRemoved (all
three), runtime.onStartup (all three), alarms.Alarm (all three, and this
overturned a stale claim in webext-meta-types' current declarations),
runtime.getURL behavior (WebKit only: Chrome/Firefox signature-only),
Permissions dictionary (reused, row 3), runtime.id (reused, row 6).

**Declaration/schema-confirmed but not traced into implementation**:
commands.Command's field-level optionality for WebKit, runtime.getURL's exact
resolution algorithm for Chrome and Firefox.

**Investigated and rejected** (declaration or metadata showed real
divergence, not spec-able as identical): tabs.TabStatus, windows.WindowState,
windows.WindowType enums.

**Not determined this pass** (no claim made either way): cookies.CookieStore,
runtime.PlatformInfo, manifest keys `icons`, `options_ui`,
`content_security_policy`.

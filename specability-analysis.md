# WebExtensions areas ready for w3c/webextensions/index.bs

Analysis only. No spec text drafted, and neither `webext-meta-types` nor
`safari-webextension-types` was modified to produce it.

Ranking criterion: signature identity across Chrome, Firefox, Safari, not mere
three-engine presence. A candidate only ranks high where members share name,
arity, parameter order, per-parameter optionality, parameter and return
*shape*, and (for events) listener signature.

## Verdict, before the detail

Two things clear the bar. Everything else does not, and the reasons are listed
per namespace below.

1. **Cross-cutting: promise/callback duality.** Target: the empty "Promises
   and callbacks" heading in index.bs. Strong evidence, described below.
2. **Per-namespace: `permissions`.** Target: a new namespace section. This is
   the only namespace where every commonly-named function is signature-identical
   (arity, optionality, parameter shape, return shape) across all three engines,
   with one minor Firefox-only field on one return type.

`storage` (specifically the `onChanged` event and the `local`/`sync`/`session`
CRUD core) comes close and is named as a second-tier, partial candidate with
its specific gap quoted. `alarms` and `scripting` looked like Tier-A candidates
on an earlier presence-only pass (100% of named members shared)
but do not survive a signature diff: the actual per-parameter and per-return
shapes diverge in ways that matter to an author, and those divergences are
quoted below.

---

## 1. The data-quality question, answered first

**Question:** does webext-meta-types' Safari data support a parameter/return
*shape* comparison, or only name/arity/optionality?

**Answer: it supports shape comparison for the namespaces this report ranks,
because the current pinned Safari source has zero unresolved algorithmic
guesses left: but that was not always true, and the mechanism that got it
there is worth naming because it bounds how much to trust it.**

- Where the Safari data actually comes from: `safari-webextension-types`
  (vendored at `webext-meta-types/package.json:69`, pinned to commit
  `90cd434d03c9cd23bf031a158beeb5f99980652f`, filtered to what the Safari 26.4
  WebKit tag declares: `webext-meta-types` commit `14958a6`). Its own README
  says it is "generated directly from WebKit's upstream WebIDL interface
  declarations" (`safari-webextension-types/README.md:13`) and that "Existence
  comes from the WebKit tag of the last shipped Safari" (`README.md:16`).
- That WebIDL, read raw, is exactly as thin as an initial excerpt shows:
  names, arity, optionality, but payload types erased behind `any` /
  `NSDictionary` / `NSObject` and every operation nominally returning `void`
  with `[ReturnsPromiseWhenCallbackIsOmitted]`. **The generator does not stop
  there.** It also reads WebKit's Objective-C implementation
  (`Source/WebKit/WebProcess/Extensions/API/Cocoa/*.mm`) to recover the actual
  parameter validation table and callback payload for each operation, and
  requires a source citation for every recovered type
  (`safari-webextension-types/scripts/generate.py:1818-1832`, the
  `PARAMETER_TYPES` table; `EVENT_PAYLOADS`/`ATTRIBUTE_PAYLOADS` at
  `generate.py:1791-1816` for event listener shapes).
- **This was not always trustworthy, and there is a written postmortem about
  it failing**: `safari-webextension-types/POSTMORTEM-algorithmic-return-types.md`
  documents four wrong return types that shipped because an earlier version
  guessed a return type from the *verb in the operation's name*
  (`get`, `create`, `update`...) rather than reading the implementation: `webNavigation.getFrame` was typed with the wrong dictionary, `windows.getLastFocused`
  was typed `void` when it actually resolves a window, `menus.update` was typed
  to resolve `MenuItemProperties` when it resolves nothing, `bookmarks.get` was
  typed to resolve one node when it resolves an array. The postmortem's own
  words: "Computing an answer is not deriving one."
- **The current state, checked directly, not assumed**: three ratchet files
  track what is still guessed rather than read: `safari-webextension-types/unresolved-payloads.txt`,
  `unverified-parameters.txt`, `unverified-returns.txt`. As of this session
  (repo HEAD `e2269d4`, both files' git history last touched 2026-08-16), **all
  three contain zero non-comment entries**: every operation's return type and
  every named parameter's type has a citation into the `.mm` source, verified
  by `git log -1 --format=%H\ %ad -- unresolved-payloads.txt` → commit
  `5027809`, 2026-08-16. The ratchet is enforced both ways in the build
  (`check_ratchet` and `check_read_namespaces_are_read`,
  `generate.py:3185-3253`): a name that stops qualifying and isn't removed from
  the file fails the build, and a name that newly needs a guess and isn't added
  fails the build. That is a real, checked invariant, not a stale snapshot.
- `READ_NAMESPACES`: namespaces whose *return* shapes have been read against
  the `.mm`, not composed from a name pattern: is
  `{action, alarms, bookmarks, commands, cookies, declarativeNetRequest, dom,
  extension, menus, offscreen, permissions, runtime, scripting, sidePanel,
  i18n, sidebarAction, tabs, test, webNavigation, windows}`
  (`safari-webextension-types/scripts/generate.py:186-206`). **`storage` is
  not in this set.** Its types are not wrong, but they were not the subject of
  the read-and-cite pass either; see the `storage` finding below, where the
  actual output uses honest generics rather than a name-pattern guess.
- **Where the data is still honestly weak rather than wrong**: some read
  operations resolved to `unknown` because the implementation genuinely does
  not specify a fixed shape, and the generator widens instead of guessing. One
  example is quoted in section 3 (`cookies.onChanged` in Safari types as
  `(...args: unknown[]) => void`). That is the right kind of caveat: the
  claim of "no fixed shape" is itself evidence-backed, but it means signature
  comparison for that one member is not possible from this data: say so, not
  guess past it.
- **Net**: for the 20 `READ_NAMESPACES`, the signature diffs below compare
  real recovered shapes on the Safari side, not name-pattern guesses, and the
  ratchet means the paper trail is current. For any namespace outside that set
  (`storage` among the ones this report otherwise likes), treat a "match" as
  weaker evidence than for a `READ_NAMESPACES` member: noted inline.

---

## 2. Cross-cutting candidate: promises vs. callbacks

**Target heading**: "Promises and callbacks" (currently empty in index.bs).

**Evidence, with counts.** Across every namespace inspected for this report: `alarms`, `scripting`, `windows`, `cookies`, `storage`, `action`, `permissions`: the same shape repeats without exception:

- Chrome and Safari each declare, per operation, one Promise-returning overload
  and one or more callback-taking overloads whose callback is the operation's
  **trailing** parameter and is **optional** in Chrome, and observed as
  required-but-last in Safari's callback overloads (Safari never makes the
  callback itself optional; it declares a separate promise-only overload
  instead). Argument order before the callback is identical between the
  callback form and the Promise form in every case checked.
- Firefox's declared types (`@types/firefox-webext-browser`) expose **only**
  the Promise-returning form for every operation checked: no callback overload
  appears anywhere in `alarms`, `scripting`, `windows`, `cookies`, `storage`,
  `action`, or `permissions` in `webext-meta-types/dist/firefox-only.d.ts`.
  (Firefox's `chrome.*` compatibility shim does accept callbacks at runtime per
  MDN, but the vendored type package does not model that surface: this is a
  gap in the *types*, not necessarily in the runtime, and should be stated as
  such rather than as "Firefox doesn't support callbacks.")
- Quoted example, `alarms.clearAll`:
  - Chrome (`dist/chrome-only.d.ts:655,659`):
    `export function clearAll(): Promise<boolean>;` and
    `export function clearAll(callback?: (wasCleared: boolean) => void): void;`
  - Safari (`dist/safari-only.d.ts:314,318`):
    `export function clearAll(callback: (result: boolean) => void): void;` and
    `export function clearAll(): Promise<boolean>;`
  - Firefox (`dist/firefox-only.d.ts:279`):
    `export function clearAll(): Promise<boolean>;` only.

**What a spec section can assert**: the promise-returning form is the common
signature across all three engines, argument order is stable between the two
calling conventions where both exist, and the callback is always the last
parameter. **What it cannot assert without a runtime check the types cannot
provide**: whether Firefox's `chrome.*` shim callback ordering matches Chrome's
exactly: the type data is silent on that because the Firefox package does not
type it at all. That gap should be named in the section, not silently assumed
away.

---

## 3. Per-namespace candidate: `permissions`

**Target**: a new `permissions` section in index.bs (none exists today).

**Coverage floor** (`webext-meta-types/coverage.json`, function+variable
kinds only): 8 total named members, Chrome 8, Firefox 6, Safari 6, all three
6/8 (75%). `permissions` is in `READ_NAMESPACES` on the Safari side, so this
is a full-confidence comparison, not a name-pattern guess.

**Signature diff, the 6 members common to all three:**

| member | Chrome | Firefox | Safari | verdict |
|---|---|---|---|---|
| `onAdded` | `Event<(permissions: Permissions) => void>` | `WebExtEvent<(permissions: Permissions) => void>` | `Event<(permissions: Permissions) => void>` | identical payload shape, wrapper type name differs only |
| `onRemoved` | same shape as `onAdded` | same | same | identical |
| `contains` | `(permissions: Permissions): Promise<boolean>` | `(permissions: AnyPermissions): Promise<boolean>` | `(permissions: Permissions): Promise<boolean>` | identical arity/return; Firefox widens the parameter type (see below) |
| `request` | `(permissions: Permissions): Promise<boolean>` | `(permissions: Permissions): Promise<boolean>` | `(permissions: Permissions): Promise<boolean>` | identical, all three |
| `remove` | `(permissions: Permissions): Promise<boolean>` | `(permissions: Permissions): Promise<boolean>` | `(permissions: Permissions): Promise<boolean>` | identical, all three |
| `getAll` | `(): Promise<Permissions>` | `(): Promise<AnyPermissions>` | `(): Promise<Permissions>` | identical arity/return; Firefox's resolved type carries one extra optional field |

Citations for the three-way quote above:
`dist/chrome-only.d.ts:9358-9435`, `dist/firefox-only.d.ts:2394-2414`,
`dist/safari-only.d.ts:801-837`.

**The `Permissions` dictionary itself**, structurally:

- Chrome (`dist/chrome-only.d.ts`, `interface Permissions`):
  `{ permissions?: string[]; origins?: string[] }`
- Safari (`dist/safari-only.d.ts:1714`-adjacent block): same two fields, same
  optionality, same element type (`string[]`).
- Firefox: `{ permissions?: OptionalPermission[] | OptionalOnlyPermission[];
  origins?: MatchPattern[]; data_collection?: OptionalDataCollectionPermission[] }`: same two core fields at the same optionality, the array element type is a
  manifest-key string-literal union rather than a bare `string` (a strictly
  narrower, not incompatible, type), plus one Firefox-only optional field,
  `data_collection`, absent from Chrome and Safari.

**Divergences to write around, stated plainly**: (1) Firefox narrows
`permissions`/`origins` element types to its own manifest-key enums instead of
`string`; a spec would either widen to `string` (matching Chrome/Safari) or
pick Firefox's narrower typing and note Chrome/Safari don't enforce it. (2)
Firefox's `getAll`/`contains` return/accept an extra optional
`data_collection` field the other two engines don't have. (3) The event
wrapper type name differs (`Event` vs `WebExtEvent`) but this is a
type-package naming artifact, not a behavioral difference: the payload shape
inside it is identical in all three.

Neither divergence blocks a spec: both are "one engine adds an optional
field/narrows a type," which a spec can describe as an extension point rather
than a conflict. This is why `permissions` is the strongest candidate found.

---

## 4. Second-tier partial candidate: `storage` (`onChanged` and core CRUD)

**Caveat first**: `storage` is **not** in Safari's `READ_NAMESPACES`
(`generate.py:186-206`), so its Safari types were not the subject of the
read-the-implementation pass the way `permissions`/`alarms`/`scripting`/etc.
were. What ships for `storage.StorageArea.get<T>` is a generic
(`get<T = Record<string, unknown>>(keys?): Promise<T>`,
`dist/safari-only.d.ts` inside the `storage` block): an honest "I don't know
the shape, it's generic," not a wrong guess, but also not a citation-backed
concrete type the way `permissions.request`'s `boolean` return is. Treat the
match below as good but one notch below `permissions`'s evidence class.

**Coverage floor**: 5 total members, Chrome 5, Firefox 5, Safari 4, all three
4/5 (80%).

**`onChanged` is signature-identical across all three, verbatim**:

- Chrome (`dist/chrome-only.d.ts:12421`):
  `export const onChanged: events.Event<(changes: Record<string, StorageChange>, areaName: string) => void>;`
- Firefox (`dist/firefox-only.d.ts:3122`):
  `export const onChanged: events.Event<(changes: Record<string, StorageChange>, areaName: string) => void>;`
- Safari (`dist/safari-only.d.ts:1199`):
  `export const onChanged: events.Event<(changes: Record<string, storage.StorageChange>, areaName: string) => void>;`

The only difference is the namespace qualifier on the type name
(`StorageChange` vs `storage.StorageChange`), which is the same type either
way. This is the single cleanest three-way match found anywhere in this
review.

**The core CRUD methods (`get`, `set`, `remove`, `clear`, `getBytesInUse`,
`getKeys`) match closely** between Chrome and Safari (both declare `local` /
`sync` / `session` directly as `StorageArea`, with matching generic `get<T>`,
`set(items): Promise<void>`, `remove(keys): Promise<void>`,
`clear(): Promise<void>` signatures). **Firefox diverges structurally, not
just cosmetically**: `local`/`sync`/`session` are typed via
`LocalStorageArea` / `SyncStorageAreaWithUsage` / `SessionStorageAreaWithUsage`
(`dist/firefox-only.d.ts:3106-3160`), which extend a *different* base
interface, `StorageAreaWithUsage`, whose `get` resolves
`Promise<{ [key: string]: /* TODO: Upstream type uses any */ any }>` instead
of the generic `Promise<T>` Chrome and Safari both use. That's a genuinely
looser return type on Firefox specifically for the areas developers actually
use (`local`/`sync`/`session`), flagged in the upstream package itself with a
`TODO: Upstream type uses any` comment, not something this project invented.

**Divergence to write around**: a spec section on `storage.<area>.get` can
standardize the generic `Promise<T>` shape Chrome and Safari already share and
treat Firefox's looser typing as a known type-package gap rather than a
behavioral difference (Firefox's runtime almost certainly resolves the same
shape; its *types* just don't say so).

---

## 5. What does not clear the bar, and why (the namespaces that looked strong on presence alone)

These were the top of the presence-only ranking (percent of same-named members
shared by all three engines, from `coverage.json`, `function`+`variable` kinds
only). Signature diffing knocks all of them back out of "spec-able now."

| namespace | members | Chrome | Firefox | Safari | shared by all 3 | % shared | why it doesn't clear the signature bar |
|---|---:|---:|---:|---:|---:|---:|---|
| `scripting` | 7 | 7 | 7 | 7 | 7 | 100.0 | `executeScript` is generic and function-typed (`func?: (...args: Args) => R`) in Chrome/Firefox, but `unknown`-typed in Safari: the one thing this namespace exists for (injecting a typed function) isn't comparably typed. `InjectionResult` inverts optionality (`documentId`/`frameId` optional+required→required+optional across engines) and Safari's `result` is required-nullable vs Chrome/Firefox's optional. `RegisteredContentScript.world` is `"main"\|"isolated"\|"MAIN"\|"ISOLATED"` in Safari vs `"ISOLATED"\|"MAIN"` only in Chrome/Firefox: a real acceptable-value divergence, not cosmetic. See quotes below. |
| `alarms` | 6 | 6 | 6 | 6 | 6 | 100.0 | Core CRUD (`get`, `getAll`, `clear`, `clearAll`) *is* signature-identical (see below): this namespace is close. But `Alarm.name`/`Alarm.scheduledTime` are required in Chrome/Firefox and optional in Safari, and `persistAcrossSessions` is Chrome-only on both `Alarm` and `AlarmCreateInfo`. |
| `windows` | 13 | 13 | 12 | 12 | 12 | 92.3 | `onCreated`/`onRemoved`/`onFocusChanged` are a Chrome-only `CustomChromeEvent` type carrying an extra `filters` parameter on `addListener` that Firefox/Safari's plain `Event` doesn't have. `Window.alwaysOnTop` is Chrome/Firefox-only, absent from Safari. `create()` resolves `Promise<Window>` in Chrome/Firefox, `Promise<Window \| undefined>` in Safari. |
| `cookies` | 7 | 7 | 6 | 6 | 6 | 85.7 | `get()` resolves `Promise<Cookie \| undefined>` in Chrome vs `Promise<Cookie \| null>` in Firefox and Safari (Firefox/Safari agree, Chrome differs). `remove()` resolves three different shapes in three engines: Chrome an inline object, Firefox `_RemoveReturnDetails \| null`, Safari `Cookie \| null`. `onChanged`'s payload is fully typed and identical in Chrome/Firefox but widens to `(...args: unknown[]) => void` in Safari: a case where the underlying WebKit implementation apparently doesn't expose a fixed shape, not a guess (see §1). |
| `action` | 18 | 18 | 17 | 14 | 14 | 77.8 | `onClicked` takes `(tab: Tab) => void` in Chrome and Safari but `(tab: Tab, info?: OnClickData) => void` in Firefox: an extra optional click-modifier parameter Chrome/Safari don't have. Safari covers only 14/18 named members at all, the lowest of the three. |
| `webRequest` | 14 | 12 | 13 | 9 | 9 | 64.3 | Safari covers 9/14 named members; not diffed member-by-member for this report (time-boxed), flagged only as "does not clear presence floor comfortably," let alone signature identity. |
| `webNavigation` | 11 | 11 | 10 | 7 | 7 | 63.6 | Same as above: Safari at 7/11, not diffed further. |
| `tabs` | 49 | 37 | 44 | 27 | 25 | 51.0 | Largest namespace, lowest common fraction of the ones with any three-way overlap at all; not diffed member-by-member here: 49 members is out of scope for a time-boxed manual diff, and 51% shared already fails "near total." |
| `runtime` | 37 | 33 | 28 | 21 | 18 | 48.6 | Same reasoning as `tabs`. |
| `commands` | 6 | 2 | 6 | 3 | 2 | 33.3 | Safari and Chrome both cover a minority of the named members; not spec-able from this data. |
| `declarativeNetRequest` | 28 | 26 | 21 | 12 | 9 | 32.1 | Safari covers well under half the surface (12/28); not spec-able from this data. |

**Quoted divergences for `scripting.executeScript`** (the headline example,
`dist/*.d.ts`):

- Chrome (`dist/chrome-only.d.ts:10878`, identical text in `dist/firefox-only.d.ts:2912`):
  `export function executeScript<R = unknown, Args extends unknown[] = unknown[]>(injection: ScriptInjection<Args, R>, callback?: (results: InjectionResult<Awaited<R>>[]) => void): Promise<InjectionResult<Awaited<R>>[]>;`
- Safari (`dist/safari-only.d.ts:1081,1085`):
  `export function executeScript(details: scripting.ScriptInjection, callback: (result: scripting.InjectionResult[]) => void): void;` and
  `export function executeScript(details: scripting.ScriptInjection): Promise<scripting.InjectionResult[]>;`
  where Safari's `ScriptInjection.func` is typed `unknown`, not the generic
  callable Chrome and Firefox share.

Chrome and Firefox are byte-for-byte identical on this signature. Safari is a
structurally different, non-generic shape. That is the opposite of what the
100%-presence number suggested.

**Quoted divergence for `alarms.Alarm`**:

- Chrome (`dist/chrome-only.d.ts:539`):
  `interface Alarm { name: string; scheduledTime: number; periodInMinutes?: number; persistAcrossSessions: boolean; }`
- Firefox (`dist/firefox-only.d.ts:239`):
  `interface Alarm { name: string; scheduledTime: number; periodInMinutes?: number | undefined; }`
- Safari (`dist/safari-only.d.ts:245`):
  `interface Alarm { name?: string; periodInMinutes?: number; scheduledTime?: number; }`

Chrome and Firefox agree `name`/`scheduledTime` are required; Safari marks
both optional. `persistAcrossSessions` exists only in Chrome.

**What alarms gets right**: the core CRUD, quoted for completeness, is
genuinely identical on the Promise form:

- `get`: Chrome `dist/chrome-only.d.ts:606` region resolves
  `Promise<Alarm | undefined>`; Firefox `dist/firefox-only.d.ts:267`
  `get(name?: string): Promise<Alarm | undefined>`; Safari
  `dist/safari-only.d.ts:290` `get(name?: string): Promise<Alarm | undefined>`.
  Identical in all three.
- `getAll`, `clear`, `clearAll`: identical arity/optionality/return type in
  all three (`dist/chrome-only.d.ts:624,637,655`,
  `dist/firefox-only.d.ts:271,275,279`, `dist/safari-only.d.ts:298,310,318`).

If a spec wanted to standardize only the four read/clear operations of
`alarms` and leave `Alarm`'s exact optionality and `persistAcrossSessions` as
engine-defined extensions, that subset clears the bar. The namespace as a
whole does not.

---

## 6. Namespaces with no three-engine overlap at all (out of scope for any index.bs section right now)

From `coverage.json`, namespaces where zero same-named member is declared by
all three engines: **94 of 110** namespaces with any function/variable
members. Two more failure shapes worth naming, both computed directly from
`coverage.json`:

- **21 namespaces are Chrome+Firefox only, zero Safari overlap**: `bookmarks`,
  `browsingData`, `devtools.inspectedWindow`, `devtools.network`,
  `devtools.panels`, `dns`, `dom`, `downloads`, `history`, `identity`, `idle`,
  `management`, `menus`, `notifications`, `omnibox`, `proxy`, `search`,
  `sessions`, `tabGroups`, `topSites`, `userScripts`. Several of these
  (`bookmarks`, `notifications`, `offscreen`, `sidebarAction`, `sidePanel`)
  are Safari-absent for a documented reason, not a data gap: WebKit's own
  source says so, cited in
  `webext-meta-types/excluded-namespaces.json`: e.g. `notifications`
  quotes `"Notifications are currently only available in test mode as an
  empty stub."` from
  `Source/WebKit/WebProcess/Extensions/API/WebExtensionAPINamespace.cpp` at
  WebKit ref `0136fa2b7cf669ab6bc8e715727e6a78bf5f24ba`. These are not
  candidates until Safari ships the surface at all.
- **73 namespaces are single-engine only**: 51 Chrome-only (mostly
  enterprise/ChromeOS/legacy-Chrome-Apps surface: `sockets.*`, `system.*`,
  `enterprise.*`, `platformKeys`, `certificateProvider`, etc.), 21
  Firefox-only (`privacy.*`, `telemetry`, `theme`, `geckoProfiler`, etc.), and
  1 Safari-only (`devtools`, discussed as a data artifact in §7, not a real
  Safari-exclusive capability).

None of these are spec candidates from this data; several by design
(vendor-specific platform integration), not by data gap.

---

## 7. Data-quality caveats, stated explicitly

- **BCD disagrees with this data 124 times.**
  `webext-meta-types/BCD-DISCREPANCIES.md` cross-checks `coverage.json`
  against `@mdn/browser-compat-data` (`scripts/audit-bcd.ts`, a devDependency,
  not part of the main `npm run build`: README's own words: BCD is used only
  for this audit, not as a data source). Of note for namespaces this report
  touches: BCD says Firefox supports `webNavigation.onTabReplaced`
  (`BCD-DISCREPANCIES.md:134`) and `userScripts.execute`
  (`:133`) where the generated types say Firefox does not: outside the
  namespaces ranked above, but a reminder that "the types say no" is not
  always "the browser doesn't do it," it can mean "the type package hasn't
  caught up." Six of the fourteen listed conflicts are all
  `devtools.inspectedWindow.*`: types say Safari NO, BCD says Safari YES
  (`BCD-DISCREPANCIES.md:125-130`). That namespace was excluded from this
  report's candidate list on presence grounds already (0% three-way overlap,
  Chrome+Firefox only per §6), but if BCD is right, Safari's DevTools
  inspection surface may be under-counted here, not absent: worth a follow-up
  before writing it off entirely.
- **A namespace-grouping artifact, not a real capability**: `coverage.json`
  shows `devtools` as a Safari-only namespace with 3 members
  (`inspectedWindow`, `network`, `panels`). Reading
  `webext-meta-types/dist/safari-only.d.ts`, these are properties on a
  `devtools` variable, while Chrome/Firefox declare `devtools.inspectedWindow`
  etc. as their own sub-namespaces. Same information, different grouping in
  the IR the generator builds. Do not read this as "Safari has a `devtools`
  API Chrome/Firefox lack."
  `webext-meta-types/dist/merge-issues.json` independently records two
  places the merge itself couldn't reconcile shapes at all: `events.Event`'s
  type parameters differ across all three packages, and
  `scripting.ScriptInjection`'s generic parameters exist in Chrome/Firefox but
  not Safari (consistent with the `executeScript` finding in §5): "Safari
  member forms omitted" is the tool's own note there.
- **Firefox's type package is Promise-only** where Chrome and Safari both
  model callback and Promise forms (§2): treat any "Firefox lacks callback
  support" claim in this report or elsewhere as a claim about the *type
  package*, since MDN documents Firefox's `chrome.*` shim accepting callbacks
  at runtime, and this dataset does not model that surface at all.
- **Cross-cutting manifest-level areas (match patterns, globs, host
  permissions, version numbering, extension ID uniqueness) were not diffed
  for this report.** These were flagged as promising cross-cutting targets in an
  earlier pass; the merged data does carry manifest-level types (a `_manifest`
  namespace, a `MatchPattern` type in Firefox's package, permission strings
  elsewhere) that could support this analysis, but doing a real signature diff
  on them was out of the time box for this pass. Flagging as unevaluated
  rather than claiming coverage.
- **`tabs`, `runtime`, `webRequest`, `webNavigation`, `declarativeNetRequest`,
  `commands`** were scored on presence only (the numeric table in §5); no
  member-by-member signature diff was done for these given their size (28-49
  members each) and given that none cleared even the presence floor
  comfortably enough to justify the diff effort within this pass. If any of
  these becomes a priority, the same extraction method used for `alarms` /
  `scripting` / `windows` / `cookies` / `storage` / `action` / `permissions`
  in this report (namespace-block extraction from
  `dist/{chrome,firefox,safari}-only.d.ts`, cross-checked against
  `dist/metadata.json`'s per-member `note` field) applies directly.

---

## 8. Method, for reproducibility

- Presence/coverage floor: `webext-meta-types/coverage.json`, filtered to
  `kind` in `{function, variable}` (methods, properties, and events: `interface`/`type` entries excluded as non-runtime scaffolding). Generated
  by `scripts/generate-coverage.ts` from the same IR the generator itself uses
  (`buildIr`, `src/generator.ts:825` for `BROWSER_ORDER = [chrome, firefox,
  safari]`), so the coverage report cannot drift from `dist/index.d.ts`.
- Signature diff: per-namespace blocks extracted from
  `dist/chrome-only.d.ts`, `dist/firefox-only.d.ts`, `dist/safari-only.d.ts`
  by brace-depth parsing (these are the pruned, single-vendor subsets the
  project ships, each asserted by `npm run check:pruned` to be a strict
  subset of `dist/index.d.ts`), cross-checked against `dist/metadata.json`'s
  per-member `note` field (e.g. `"optional in Safari, required in Chrome,
  Firefox"`, `"type differs between browsers"`) and per-overload `supported`
  arrays.
- `dist/`, `coverage.json`, and `COVERAGE.md` were already committed and
  current; no rebuild was necessary or performed.

# Version number handling: three-engine source findings

All line numbers are from the Chromium, Gecko and WebKit source trees read for this
task (read only, not built, not modified).

## 1. Accepted grammar

### Chromium

The `version` key is read as a string and passed straight to `base::Version`,
then subjected to one extra extension-specific constraint on top of it.

- Parsing: `base::Version(std::string_view version_str)` splits on `.` with
  `SplitStringPiece` and parses each piece with `base::StringToUint` into a
  `uint32_t` (`base/version.cc:27-56`, constructor at `base/version.cc:98-105`).
- Component count: `base::Version` itself allows any number of components
  (`IsValid()` only requires the vector be non-empty, `base/version.cc:110-112`).
  The extensions layer adds the real cap: `extensions/common/extension.cc:701`,
  `if (!version_.IsValid() || version_.components().size() > 4)` rejects
  anything with more than 4 components. Minimum is 1 component.
- Component range: each component is parsed as `unsigned int`, statically
  asserted equal in size to `uint32_t` (`base/version.cc:50-52`), so the
  representable range per component is 0 to 4294967295. No code anywhere in
  `extensions/common/extension.cc` or `base/version.cc` imposes a smaller
  numeric ceiling.
  - The human-readable error string disagrees with the code:
    `extensions/common/manifest_constants.h:634-636` reads "It must be
    between 1-4 dot-separated integers each between 0 and 65536." A
    repo-wide grep for `65536`/`65535` in `extensions/` and
    `chrome/common/extensions/` turns up nothing that enforces that bound;
    the only code-level ceiling is the `uint32_t` component type and the
    4-component cap. Treat the "0 and 65536" claim in the error text as
    aspirational/stale, not as enforced behavior, unless a reviewer finds
    a check this search missed.
- Leading zeros: rejected only in the first component. In
  `ParseVersionNumbers` (`base/version.cc:35-48`), the canonical-form check
  `if (it == numbers.begin() && NumberToString(num) != *it) return false;`
  only runs on the first split piece. A leading zero in a later component
  parses fine at this layer.
  - The extensions layer turns a non-canonical (but parseable) string into a
    warning, not a rejection: `extensions/common/extension.cc:705-713`
    compares the original string against `version_.GetString()` (the
    canonical form) and if they differ, appends an `InstallWarning` with
    message template `kVersionFormatting` (`extensions/common/manifest_constants.h:733-734`,
    "The extension version is parsed as '%s'.") but still succeeds.
  - Confirmed by the unit test `ExtensionTest.ExtensionVersionFormat`
    (`extensions/common/extension_unittest.cc:372-390`):
    `"0.0.01"` succeeds, reformatted to `"0.0.1"`; `"1.002.3"` succeeds,
    reformatted to `"1.2.3"`; but `"01"` and `"00.1"` both fail (leading
    zero in the first component).
- Non-numeric components: rejected. `StringToUint` fails for anything that
  is not purely decimal digits (`base/version.cc:40-43`).
- Sign / `+` prefix: rejected. `ParseVersionNumbers` explicitly refuses a
  component starting with `+` (`base/version.cc:36-38`), and `StringToUint`
  fails on `-` since it parses unsigned. Confirmed by test cases `"-1.0"`,
  `"1.-1"`, `"-0.0"` all failing (`extensions/common/extension_unittest.cc:388-390`).

Net Chromium grammar: 1 to 4 dot-separated components, each `0` to
`4294967295`, no leading zeros in the first component (leading zeros
elsewhere are silently canonicalized with a warning), no non-numeric
components, no sign characters.

### Gecko

The manifest schema declares `version` as a plain string
(`toolkit/components/extensions/schemas/manifest.json:55-59`,
`"type": "string", "optional": false, "format": "versionString"`), and the
`versionString` format validator
(`toolkit/components/extensions/Schemas.sys.mjs:1386-1400`) is advisory only:

    versionString(string, context) {
      const parts = string.split(".");
      if (
        parts.length > 4 ||
        parts.some(part => !/^(0|[1-9][0-9]{0,8})$/.test(part))
      ) {
        context.logWarning(`version must be a version string consisting of at most 4 integers ...`);
      }
      // ... Given the version is required, we always accept the value as is.
      return string;
    }

- The recommended/documented grammar (the one that avoids the warning) is:
  at most 4 dot-separated parts, each part matching `^(0|[1-9][0-9]{0,8})$`
  -- i.e. either the single digit `0`, or a run of 1 to 9 digits with no
  leading zero.
- The accepted grammar is unbounded: any string is accepted as a
  manifest `version`, including an empty string, more than 4 parts, parts
  with leading zeros, parts over 9 digits, or non-numeric parts. Only a
  warning is logged (`Schemas.sys.mjs:1395-1398`); the function unconditionally
  `return string` unchanged. `logWarning` can become a hard error only if the
  caller is treating warnings as errors (`Schemas.sys.mjs:644-646`,
  `_logNormalizedWarning` at `Schemas.sys.mjs:654-660`), which is not the
  case for a normal browser install.
- `version_name` (see part 5) and non-numeric parts are legal by design
  here: Gecko's own comparator (`nsVersionComparator.cpp`) is built to
  understand alphanumeric parts, so a version string like `"1.0a1"` is
  meaningful under Gecko's semantics even though it would fail Chromium's
  parser outright.

### WebKit

`WebExtension::populateDisplayStringsIfNeeded` reads `version` with a bare
`getString`, with no splitting, no numeric parsing, and no format check at
all (`Source/WebKit/UIProcess/Extensions/WebExtension.cpp:938-953`):

    m_version = manifestObject->getString(versionManifestKey);
    ...
    if (m_version.isEmpty())
        recordError(createError(Error::InvalidVersion));

The only condition checked is emptiness. Any non-empty string -- any number
of components, any component values, letters, punctuation, whatever JSON
allows in a string -- is accepted verbatim as the extension's version.
WebKit performs no grammar validation whatsoever.

## 2. Comparison algorithm

### Chromium: base::Version::CompareTo / CompareVersionComponents

Pure numeric tuple compare, component by component, left to right, with the
shorter version treated as zero-padded to the longer one's length
(`base/version.cc:58-86`):

    for (size_t i = 0; i < count; ++i) {
      if (components1[i] > components2[i]) return 1;
      if (components1[i] < components2[i]) return -1;
    }
    // tail of the longer vector compared against implicit zeros

Because a Chromium-valid version string can never contain a non-numeric
component (see part 1), this reduces in practice to plain numeric tuple
comparison -- there is no alphanumeric handling anywhere in this path.

### Gecko: nsIVersionComparator / mozilla::CompareVersions

Declared in `xpcom/base/nsIVersionComparator.idl:7-34`. Much richer than a
numeric tuple compare. Each dot-separated "version-part" is itself decomposed
into up to four sub-tokens:

    <number-a><string-b><number-c><string-d (everything else)>

- `numA`/`numC` are parsed with `strtol` into `int32_t` via a
  `CheckedInt<int32_t>` guard; on overflow or any `strtol` error
  (`errno != 0`), the value is silently replaced with `0`
  (`xpcom/base/nsVersionComparator.cpp:47-68`, used again for `numC` inside
  `ParseVP`, `nsVersionComparator.cpp:116`). There is no rejection path --
  an out-of-range number just becomes `0`.
- `strB`/`extraD` are compared byte-wise with `strcmp`/`strncmp`
  (`nsVersionComparator.cpp:226-266`), and "no string" sorts after "any
  string" (`ns_strcmp`/`ns_strnncmp` comment: "any string is *before* no
  string", `nsVersionComparator.cpp:227-229`).
- Special case: if `string-b` is exactly `"+"`, `numA` is incremented and
  `string-b` becomes `"pre"` (`nsVersionComparator.cpp:104-109`), matching
  the documented backward-compat rule in the IDL (`nsIVersionComparator.idl:20-21`).
- A version-part that is a bare `*` means "infinity" (`numA = INT32_MAX`,
  `nsVersionComparator.cpp:93-95`).
- The comparator loops over dot-separated parts with no upper bound on the
  number of parts (`do { ... } while (a || b);`,
  `nsVersionComparator.cpp:386-397`), unlike Chromium's hard 4-component cap.

This comparator is not a Firefox-app-version-only concern. It is used
directly on extension version strings for install/update decisions:
`toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:416-418`
(`newVersionReason`, decides `ADDON_UPGRADE` vs `ADDON_DOWNGRADE` via
`Services.vc.compare(oldVersion, newVersion) <= 0`) and
`XPIInstall.sys.mjs:4342` (`Services.vc.compare(addon.version, existingAddon.version) <= 0`
rejects an install that isn't strictly newer than an already-present addon
of the same ID).

### WebKit

No comparison algorithm exists anywhere in the read WebKit engine source.
A repo-wide grep for `compareVersions`/`CompareVersion` under
`Source/WebKit/WebProcess/Extensions` and `Source/WebKit/UIProcess/Extensions`
returns nothing. `version` is stored and surfaced as an opaque string
(`m_version`, `WebExtension.h:428`); if Safari or another embedder performs
version comparison for update decisions, that logic is not in the open
WebKit repository and is undetermined from this source tree.

### Concrete divergent ordering: Chromium vs. Gecko

Compare `"4294967295.0"` against `"1.0"`.

- Both strings are accepted as valid manifest versions by both engines:
  Chromium accepts `"4294967295.0"` because `4294967295` is exactly
  `UINT32_MAX`, fits in the `uint32_t` component type, has no leading zero,
  and the string has only 2 components (`extensions/common/extension.cc:696-704`,
  `base/version.cc:40-43`). Gecko accepts it too, only warning because the
  first part has 10 digits, more than the recommended 9
  (`Schemas.sys.mjs:1386-1400`); the raw string is still stored and used.
- Chromium: `base::Version` parses the first component as the literal
  `uint32_t` value `4294967295`. `CompareVersionComponents` compares that
  against `1` and returns "greater" (`base/version.cc:61-86`). So Chromium
  orders `4294967295.0 > 1.0`.
- Gecko: `ParseVP` calls `ns_strtol("4294967295", ...)`
  (`nsVersionComparator.cpp:97`), which itself calls `strtol` into a
  (typically 64-bit) `long`, so `strtol` succeeds with no `errno` overflow.
  But the result is then narrowed through `CheckedInt<int32_t> result = result_long;`
  (`nsVersionComparator.cpp:62-67`); `4294967295` is larger than
  `INT32_MAX` (`2147483647`), so `result.isValid()` is false and the
  function returns `0`. `numA` for the first version-part of
  `"4294967295.0"` is therefore `0`, identical to what `"0.0"` would parse
  to. `CompareVP`/`ns_cmp` (`nsVersionComparator.cpp:269-297`) then finds
  `"4294967295.0"` numerically equal in its first part to `0`, and Gecko
  orders `4294967295.0 < 1.0` (in fact `4294967295.0 == 0.0` under
  `Services.vc.compare`).

So the same two extension version strings, both accepted by both engines,
are ordered in opposite directions: Chromium says the huge string is newer
than `1.0`; Gecko says it is older (equal to `0.0`). This is a genuine,
source-confirmed divergence, not a hypothetical.

WebKit is excluded from this specific example because it performs no
comparison in-tree at all (see above), so there is no WebKit ordering to
diverge from.

## 3. Invalid version: rejected at load, or ignored?

- Chromium: rejected. `Extension::LoadVersion`
  (`extensions/common/extension.cc:696-704`) returns `false` when the key is
  missing, unparseable, or has more than 4 components, setting
  `errors::kInvalidVersion`. `LoadRequiredFeatures` propagates that failure
  (`extensions/common/extension.cc:669-676`), and `Extension::Create`
  returns `nullptr` when `LoadRequiredFeatures` fails
  (`extensions/common/extension.cc:266-268`). The extension does not load.
- Gecko: never rejected for format. `FORMATS.versionString`
  unconditionally accepts and returns the string
  (`Schemas.sys.mjs:1386-1400`), only logging a warning for a
  non-recommended shape. An entirely missing `version` key is a
  different failure mode: the schema marks the property
  `"optional": false` (`manifest.json:55-59`), so omitting the key
  altogether is a required-property schema violation, not a version-format
  one; this document does not trace that generic required-key failure path
  further since it applies to `version` incidentally, and is not something
  specific to version validation. An empty string (`""`), by contrast, is
  present and type-correct, so it is accepted (with a format warning) --
  Gecko is the only one of the three engines where an empty `version` value
  is not itself fatal.
- WebKit: not rejected at the engine level, from what is readable here.
  `WebExtension::populateDisplayStringsIfNeeded` records an
  `Error::InvalidVersion` (`WebExtension.cpp:952-954`) when `version` is
  missing or empty, but `recordError` only appends to an `m_errors` array
  and fires KVO (`Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionCocoa.mm:281-291`).
  Whether the extension object itself is considered successfully parsed is
  governed by `WebExtension::manifestParsedSuccessfully()`, which checks
  only that the manifest JSON parsed as an object
  (`WebExtension.cpp:353-356`, `return !!manifestObject();`) -- it does not
  consult `m_errors` or check for `InvalidVersion` specifically. The public
  API doc for the `errors` property says explicitly that callers should
  monitor it themselves (`Source/WebKit/UIProcess/API/Cocoa/WKWebExtension.h:97-100`).
  So, as far as this source tree shows, WebKit constructs the extension
  object regardless, and whether an embedder (Safari) then refuses to
  install/enable it based on `errors` is host-app policy outside the WebKit
  repository, not something enforced by the engine itself.

## 4. Is comparison observable to extension authors?

No compareVersions-style API exists in any of the three engines. Searches
for `compareVersions`/`CompareVersion` across each engine's extension API
schema directories (`chrome/common/extensions/api/*.json` and
`extensions/common/api/*.json` for Chromium, `toolkit/components/extensions/schemas/*.json`
for Gecko, the WebKit `Interfaces/*.idl` set) turn up nothing. Version
comparison is purely an install/update-time browser concern, not something
exposed to extension JavaScript in any engine.

`runtime.getManifest().version` returns the raw, uncanonicalized string
exactly as authored, in all three engines:

- Chromium: `RuntimeHooksDelegate::HandleGetManifest` converts
  `script_context->extension()->manifest()->value()` -- the parsed manifest
  dict -- directly to a V8 value (`extensions/renderer/api/runtime_hooks_delegate.cc:475-488`).
  No re-serialization through `base::Version`.
- Gecko: `getManifest() { return Cu.cloneInto(extension.manifest, ...); }`
  (`toolkit/components/extensions/child/ext-runtime.js:129-130`) clones the
  raw manifest object; `versionString`'s formatter never rewrites the string
  (see part 1), so it is the literal authored value.
- WebKit: `WebExtensionAPIRuntime::getManifest()` returns
  `extensionContext()->manifest()` directly
  (`Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:173-178`).

`runtime.getVersion()` diverges between engines:

- Chromium does canonicalize here.
  `RuntimeHooksDelegate::HandleGetVersion` returns
  `script_context->extension()->VersionString()`
  (`extensions/renderer/api/runtime_hooks_delegate.cc:490-499`), and
  `Extension::VersionString()` returns `version_.GetString()`
  (`extensions/common/extension.cc:526-528`) -- the canonical `base::Version`
  string, so for an extension authored with `"version": "1.002.3"`,
  `getManifest().version` is `"1.002.3"` but `getVersion()` is `"1.2.3"`.
- Gecko has no `runtime.getVersion()` at all. A repo-wide grep for
  `getVersion` under `toolkit/components/extensions/` finds nothing; the
  method is simply not implemented for this namespace in Gecko.
- WebKit's `getVersion()` re-reads the raw manifest string directly
  (`manifest->getString(versionKey)`,
  `WebExtensionAPIRuntimeCocoa.mm:180-184`), identical to
  `getManifest().version` -- WebKit has no canonical form to differ from,
  since it never parses `version` into components in the first place.

## 5. version_name vs version

- Chromium: supported, optional, purely a display string, and entirely
  separate from the `version_` object used for comparisons/updates.
  `VersionNameHandler::Parse` requires the value be a string if present
  (else `kInvalidVersionName`,
  `extensions/common/manifest_handlers/version_name_info.cc:30-37`); an
  empty `version_name` is treated as though it were absent -- it is not even
  stored (`version_name_info.cc:40-43`).
- Gecko: not implemented as a manifest key. There is no `version_name`
  property in `WebExtensionManifest`
  (`toolkit/components/extensions/schemas/manifest.json`), and unrecognized
  top-level manifest properties are only warned about, not rejected
  (`"additionalProperties": { "$ref": "UnrecognizedProperty" }`, resolving
  to a `type: "any"` entry annotated `"deprecated": "An unexpected property
  was found..."`, `manifest.json:891-894`). A repo-wide grep for
  `version_name`/`versionName` across `toolkit/components/extensions/` and
  `browser/components/extensions/` turns up exactly one hit: a description
  string in the `management.json` API schema for an (optional) `versionName`
  field on `ExtensionInfo` (`management.json:78-82`). But the actual
  implementation of `browser.management.get()`/`getSelf()`
  (`toolkit/components/extensions/parent/ext-management.js`) only ever sets
  `version: addon.version` (line 54) -- no code anywhere sets `versionName`.
  So Gecko currently exposes no functioning `version_name`/`versionName`
  path in either direction (manifest key in, or API field out); the
  `management.json` field appears to be vestigial/aspirational.
- WebKit: supported. `m_displayVersion` is read directly from the
  `version_name` manifest key, falling back to `m_version` (the real
  `version` string) when `version_name` is absent or empty
  (`WebExtension.cpp:944-951`). Purely a display value, matching the naming
  (`displayVersion`) and the public API doc, which calls it "the localized
  extension display version"
  (`Source/WebKit/UIProcess/API/Cocoa/WKWebExtension.h:130`). No comparison
  or validation logic touches it beyond the fallback.

## Summary table

| | Chromium | Gecko | WebKit |
|---|---|---|---|
| Components | 1-4, hard cap | up to 4 recommended, unlimited accepted | unlimited (opaque string) |
| Component range | 0-4294967295 (uint32_t) | int32_t internally for comparison, out-of-range silently becomes 0; no cap on the accepted string | none (opaque string) |
| Leading zeros | rejected in 1st component only; elsewhere tolerated + warned + canonicalized | none rejected, non-canonical shape only warned | irrelevant, no parsing |
| Non-numeric components | rejected | first-class, meaningfully ordered | irrelevant, no parsing |
| Invalid version | extension fails to load | never rejected for format (only a required-key check applies to a wholly missing key) | not rejected by the engine itself; recorded as an error the host app may or may not act on |
| Comparison | plain numeric tuple, zero-padded | rich alphanumeric + `+`/`*` handling, int32 overflow silently clamps to 0 | none found in-tree |
| getManifest().version | raw string | raw string | raw string |
| getVersion() | canonicalized base::Version string | not implemented | raw string (same as getManifest().version) |
| version_name | supported, display only | not implemented (vestigial API field only) | supported, display only, falls back to version |

## Undetermined / out of scope for this source-only pass

- Whether Safari (the WebKit embedder) actually refuses to install/enable an
  extension whose `version` produced an `Error::InvalidVersion`. That policy
  is not in the open WebKit repository read for this task.
- Whether any comparison logic exists in Safari/App Store tooling outside
  WebKit's open-source tree for update decisions.
- Chrome Web Store server-side validation (separate from the Chromium
  browser binary) was not examined; only browser-side `extensions/common`
  code was read.
- AMO (addons.mozilla.org) server-side linting of `version` strings was not
  examined; only the Gecko browser/toolkit source was read.

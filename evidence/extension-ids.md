# Uniqueness of extension IDs: three-way source findings

Source trees read (read-only, no edits, no builds): Chromium, Gecko, WebKit. Paths
below are relative to each engine's own source root.

All line numbers were read directly from the files listed; each claim below
cites the exact file:line.

## 1. How the ID is produced

### Chromium

ExtensionId is a plain string type:

extensions/common/extension_id.h:14-16
    // If valid, uniquely identifies an Extension using 32 characters from the
    // alphabet 'a'-'p'.
    using ExtensionId = std::string;

The alphabet mapping (why a-p instead of 0-f) is defined in
components/crx_file/id_util.cc:21-36 (ConvertHexadecimalToIDAlphabet),
explicitly to avoid an all-numeric host that some software would parse as an
IP address.

The actual derivation, components/crx_file/id_util.cc:40-57:
- kIdSize = 16 (line 43): "First 16 bytes of SHA256 hashed public key."
- GenerateId(input) -> GenerateIdFromHash(crypto::hash::Sha256(input))
  (lines 49-51).
- GenerateIdFromHash(hash) hex-encodes the first 16 bytes of the hash, then
  runs it through ConvertHexadecimalToIDAlphabet (lines 53-57).

Where the input comes from, extensions/common/extension.cc:149-179
(ComputeExtensionID):
- If the manifest has a "key" (PEM public key) field, the ID is
  crx_file::id_util::GenerateId(public_key_bytes) (line 167) - i.e. a hash
  of the extension's packaging public key.
- Otherwise, unless Extension::REQUIRE_KEY is set, the ID falls back to
  crx_file::id_util::GenerateIdForPath(path) (line 179) - a hash of the
  extension's absolute filesystem path. The comment right above it
  (lines 172-174) says this exists "for development mode, because it keeps
  the ID stable across restarts and reloading the extension" when there is
  no key yet (unpacked/"Load unpacked" extensions).

GenerateIdForPath (components/crx_file/id_util.cc:65-68) normalizes the
path (uppercases Windows drive letters, MaybeNormalizePath,
lines 78-93) and hashes the path string the same way as the public-key case.

The public key itself is either author-supplied (a .pem file passed to the
packer) or generated fresh by Chrome on first pack
(extensions/browser/extension_creator.cc:261-279, GenerateKey called when
no private_key_path is given).

At install/update time, the CRX verifier re-derives the ID from the signature
block and requires it to match the package's declared ID:

components/crx_file/crx_verifier.cc:166-168
    const std::string declared_crx_id =
        id_util::GenerateIdFromHex(base::HexEncode(crx_id_encoded));

components/crx_file/crx_verifier.cc:205-208
    if (id_util::GenerateId(key) == declared_crx_id) {
      public_key_bytes = key;
    }

So a Chromium extension ID is deterministic: a hash of a public key the
developer controls (or, for unpacked dev-mode loads, a hash of the load
path).

### Gecko

The ID comes from the manifest, under browser_specific_settings.gecko.id
(and the deprecated applications.gecko.id):

toolkit/components/extensions/schemas/manifest.json:715-745
DeprecatedApplications.gecko and BrowserSpecificSettings.gecko are both
$ref: FirefoxSpecificProperties, whose id property (line 639-642) is
$ref: ExtensionID, optional: true.

toolkit/components/extensions/Extension.sys.mjs:487-489 documents that
internally the two keys are unified:
"Internally, we use the `applications` key but it is because we assign the
value of `browser_specific_settings` to `applications` in
`ExtensionData.parseManifest()`."

The manifest value is copied straight into the addon object with no
transformation:

toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:489-491
    let bss = manifest.applications?.gecko || {};
    ...
    addon.id = bss.id;

So, unlike Chromium, the developer authors the literal ID string in
manifest.json; Gecko performs no hashing or derivation from a key.

When the key is absent (toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:723-736):
1. If the package is signed, addon.id = cert.commonName (the ID baked into
   the AMO signing certificate at signing time), still checked against the
   ID regex (line 727-729, throw if it fails).
2. Otherwise, only for a TEMPORARY install (about:debugging -> "Load
   Temporary Add-on"), addon.id = generateTemporaryInstallID(aPackage.file)
   (line 734).
3. For a normal (non-temporary), unsigned package with no id and no
   certificate, no ID is assigned in this code path - Gecko has no general
   "derive from install path" fallback comparable to Chromium's.

generateTemporaryInstallID (toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:669-681):
    const hasher = CryptoHash("sha1");
    const data = new TextEncoder().encode(aFile.path);
    // Make it so this ID cannot be guessed.
    const sess = TEMP_INSTALL_ID_GEN_SESSION;
    hasher.update(sess, sess.length);
    hasher.update(data, data.length);
    let id = `${getHashStringForCrypto(hasher)}${XPIExports.XPIInternal.TEMPORARY_ADDON_SUFFIX}`;

TEMP_INSTALL_ID_GEN_SESSION (line 168-170) is
new Uint8Array(Float64Array.of(Math.random()).buffer) - a random salt
generated once per process, with the explicit comment (lines 164-167):
"This is a random number array that can be used as 'salt' when generating an
automatic ID based on the directory path of an add-on. It will prevent
someone from creating an ID for a permanent add-on that could be replaced by
a temporary add-on." Because the salt is re-randomized every process start,
this fallback ID is NOT stable across restarts, unlike Chromium's path-hash
fallback.

### WebKit

WebKit does not read any manifest key for the ID at all: a repo-wide search
for "browser_specific_settings" inside Source/WebKit/ returns zero matches.
Instead, every WebExtensionContext carries a uniqueIdentifier that is either
supplied by the embedding native app or auto-generated:

Source/WebKit/UIProcess/Extensions/WebExtensionContext.h:1095
    String m_uniqueIdentifier = WTF::UUID::createVersion4().toString();

Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:154-165
    void WebExtensionContext::setUniqueIdentifier(String&& uniqueIdentifier)
    {
        ASSERT(!isLoaded());
        if (isLoaded())
            return;
        m_customUniqueIdentifier = !uniqueIdentifier.isEmpty();
        if (uniqueIdentifier.isEmpty())
            uniqueIdentifier = WTF::UUID::createVersion4().toString();
        m_uniqueIdentifier = uniqueIdentifier;
    }

The public API surface documents this explicitly:

Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionContext.h:189-194
"A unique identifier used to distinguish the extension from other
extensions and target it for messages. ... The default value is a unique
value that matches the host in the default base URL. The identifier can be
any value that is unique. Setting is only allowed when the context is not
loaded. This value is accessible by the extension via `browser.runtime.id`
..."

So a WebKit extension's "ID" is not derived from the extension package or
manifest at all - it is a value the embedding application (e.g. Safari)
assigns, defaulting to a freshly generated random UUID if the app never
calls setUniqueIdentifier. This is a fundamentally different model from
both Chromium (derived from a key) and Gecko (authored in the manifest).

## 2. Accepted form: character set, length, case

### Chromium

components/crx_file/id_util.cc:95-109 (IdIsValid):
    if (id.size() != (crx_file::id_util::kIdSize * 2)) return false;  // 32 chars
    for (char ch : id) {
      ch = base::ToLowerASCII(ch);
      if (ch < 'a' || ch > 'p') return false;
    }

- Exactly 32 characters.
- Each character in a-p (case-insensitive: input is lowercased before the
  range check, per line 102).

### Gecko

toolkit/components/extensions/schemas/manifest.json:623-634, the
ExtensionID schema type, a two-way choice:
    { "type": "string", "pattern": "(?i)^\\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\}$" },
    { "type": "string", "pattern": "(?i)^[a-z0-9-._]*@[a-z0-9-._]+$" }

The same regex is duplicated at the runtime validation layer:

toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:176-178
    var gIDTest =
      /^(\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}|[a-z0-9-\._]*\@[a-z0-9-\._]+)$/i;

So Gecko accepts either:
- A GUID wrapped in braces, e.g. {daf44bf7-a45e-4450-979c-91cf07434c3a}
  (32 hex digits in the standard 8-4-4-4-12 grouping), or
- An "email-like" string: [a-z0-9-._]*@[a-z0-9-._]+, e.g.
  myaddon@example.org.

Both forms are matched case-insensitively ((?i) / trailing i flag). No fixed
length for the email-like form.

### WebKit

No format constraint is enforced at all beyond non-empty: setUniqueIdentifier
(WebExtensionContext.cpp:154-165, quoted above) only checks
uniqueIdentifier.isEmpty(); there is no regex or length check on a
developer-supplied value. The documented default is a standard UUID string:

Source/WTF/wtf/UUID.cpp:113-115 - UUID::toString() returns
makeString(*this), and UUID::parse (lines 117-120) documents the expected
shape as "UUIDs have the form xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx with
hexadecimal digits for x" (36 characters, hyphens at positions 8/13/18/23).

But because the app can set uniqueIdentifier to "any value that is unique"
(WKWebExtensionContext.h:191), WebKit places no character-set or length
restriction on the ID as a matter of specified behavior - only the default
generator does.

## 3. Stability across installs, machines, and packed/unpacked loads

### Chromium
- Packed (has a signing key): the ID is a pure hash of the public key
  (extension.cc:167, id_util.cc:49-51). Same key -> same ID on any machine,
  any number of installs, forever - this is exactly what
  crx_verifier.cc:205-208 checks to authorize an update.
- Unpacked / no key: ID is a hash of the absolute load path (extension.cc:179,
  id_util.cc:65-68), explicitly "to keep the ID stable across restarts and
  reloading" (extension.cc:172-174). This means the ID changes if the same
  source is loaded unpacked from a different path, or loaded packed instead
  of unpacked (different derivation entirely) - packed and unpacked loads of
  the same extension source do NOT share an ID unless the developer pins a
  "key" in the manifest for the unpacked copy.

### Gecko
- The ID is whatever the developer wrote into
  browser_specific_settings.gecko.id (XPIInstall.sys.mjs:490) - stable by
  construction across machines and installs, packed or unpacked, as long as
  the manifest is unchanged. This is developer-authored stability, not
  cryptographic derivation.
- If omitted, and the package is AMO-signed, the ID is pinned to the signing
  certificate's commonName (XPIInstall.sys.mjs:725-729) - stable across
  installs of that same signed package.
- If omitted, unsigned, and the install is TEMPORARY only, the fallback ID
  uses a per-process random salt (XPIInstall.sys.mjs:672-681,
  TEMP_INSTALL_ID_GEN_SESSION at line 168-170) and is explicitly NOT stable
  across restarts.

### WebKit
The ID (uniqueIdentifier) is generated fresh - a new random UUIDv4 - every
time a WebExtensionContext C++ object is constructed
(WebExtensionContext.h:1095), and this constructor runs whenever the
embedding app instantiates WKWebExtensionContext for that extension
(WebExtensionContextCocoa.mm:216-223). Nothing in WebKit derives this value
from the extension's manifest, its package, or a signing key - there is no
persistence of the default value across app launches inside WebKit itself.
The identifier is stable only if, and for as long as, the embedding
application explicitly calls setUniqueIdentifier with a value it generates
and persists itself before each load() (the setter is only usable pre-load:
ASSERT(!isLoaded()), WebExtensionContext.cpp:156). WebKit's on-disk storage
is itself keyed by this value (WebExtensionControllerCocoa.mm:585, see
below), so if the app fails to pin a stable ID, per-extension storage would
not be found again on the next launch.

## 4. Relation to the extension origin (index.bs's "# Extension origin")

index.bs already defines: "The extension origin is a tuple origin consisting
of an extension scheme and an extension-specific host."

### Chromium: host IS the ID

extensions/common/extension.cc:447-458
    GURL Extension::GetBaseURLFromExtensionId(const ExtensionId& extension_id) {
      return GURL(base::StrCat({extensions::kExtensionScheme,
                                url::kStandardSchemeSeparator, extension_id}));
    }
    url::Origin Extension::CreateOriginFromExtensionId(const ExtensionId& extension_id) {
      return url::Origin::Create(GetBaseURLFromExtensionId(extension_id));
    }

extension_url_ and extension_origin_ are both built directly from id()
(extension.cc:646-647 / 156-157). The host component of a
chrome-extension:// origin is the literal 32-character ID.

Caveat: Chromium separately maintains a second, per-install random
ExtensionGuid (base::Uuid::GenerateRandomV4(),
extensions/common/extension.cc:641-642) used only to build a dynamic_url_
(extension.h:280,433), an opt-in alternate resource URL for
web_accessible_resources entries marked use_dynamic_url
(extensions/common/manifest_handlers/web_accessible_resources_info.h:37,50).
This is a narrow, opt-in feature; the extension's primary origin host is
still the deterministic ID.

### Gecko: host is NOT the ID

toolkit/components/extensions/Extension.sys.mjs:361-366
"All moz-extension URIs use a machine-specific UUID rather than the
extension's own ID in the host component. This makes it more difficult for
web pages to detect whether a user has a given add-on installed (by trying
to load a moz-extension URI referring to a web_accessible_resource from the
extension). UUIDMap.get() returns the UUID for a given add-on ID."

The map is keyed by extension ID and stored in a profile-wide pref:

toolkit/components/extensions/Extension.sys.mjs:354 - UUID_MAP_PREF =
"extensions.webextensions.uuids"
Extension.sys.mjs:404-410 (UUIDMap.get): on first lookup for a given ID,
uuid = Services.uuid.generateUUID().number (braces stripped), then
persisted into the pref (this._write(map)).

And the origin is built from that UUID, not the ID:

Extension.sys.mjs:1059-1061
    if (!this.uuid) this.uuid = UUIDMap.get(this.id);
    return `moz-extension://${this.uuid}/${path}`;

So the moz-extension:// host is a random UUID, generated once per (profile,
extension-id) pair and persisted in that profile's prefs - stable across
restarts on the same profile, but different on every profile/machine, and
explicitly not the manifest ID. This is a deliberate anti-fingerprinting
design (per the comment above), independent of whether the extension is
packed or unpacked.

browser.runtime.id, however, still reports the manifest ID, not the UUID:

toolkit/components/extensions/child/ext-runtime.js:133 - id: extension.id,

### WebKit: host defaults to the ID, but both are independently overridable

Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionContextCocoa.mm:222
    m_baseURL = URL { makeString("webkit-extension://"_s, uniqueIdentifier(), '/') };

(same pattern in the GTK/GLib port:
Source/WebKit/UIProcess/Extensions/glib/WebExtensionContextGLib.cpp:35.)

So by default the origin host literally IS the uniqueIdentifier. But unlike
Chromium and Gecko, WebKit exposes both baseURL and uniqueIdentifier as
independently settable properties on the public API object, each with its
own setter and its own "must not be loaded yet" guard:

Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionContext.h:179-195
baseURL: "The default value is a unique URL using the `webkit-extension`
scheme. The base URL can be set to any URL, but only the scheme and host
will be used."
uniqueIdentifier: "The default value is a unique value that matches the
host in the default base URL."

So the spec-level invariant WebKit actually enforces is on the origin host,
not on the identifier as such (see next section) - an embedding app could in
principle set a uniqueIdentifier and a baseURL whose host doesn't match it,
though the default behavior ties them together.

browser.runtime.id returns the identifier, not the origin host directly
(they're equal by default, per above):

Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:186-190
    String WebExtensionAPIRuntime::runtimeIdentifier() {
      return extensionContext().uniqueIdentifier();
    }

## 5. Where uniqueness is enforced

All three engines enforce uniqueness only within a single local scope (a
browser profile / embedding context), not globally or via any store-level
guarantee visible in this source (store-side dedup, if any, lives in server
infrastructure not present in these trees).

### Chromium: per BrowserContext (profile)

extensions/browser/extension_registry.h:34-36
"ExtensionRegistry holds sets of the installed extensions for a given
BrowserContext. An incognito browser context and its original browser
context share a single registry."

A second install/load with an ID that's already present is NOT rejected as
a collision - it's treated as an update in place, keyed by ID:

extensions/browser/extension_registrar.cc:179-194
    const Extension* old = registry_->GetInstalledExtension(extension->id());
    if (old) {
      is_extension_installed = true;
      int version_compare_result = extension->version().CompareTo(old->version());
      if (!Manifest::IsUnpackedLocation(extension->location()) &&
          version_compare_result < 0) {
        ...  // downgrade guarded against, except for unpacked extensions
        return;
      }
    }

So "uniqueness" in Chromium means: the ID is the primary key of the
per-profile installed-extensions map; there is no separate concept of a
rejected duplicate ID, just replace-in-place governed by version comparison.

### Gecko: per-profile XPIDatabase

The add-on database is looked up by ID:

toolkit/mozapps/extensions/internal/XPIDatabase.sys.mjs:2436 -
getVisibleAddonForID(aId), 2603-2604 - getAddonByID calls it.

Update-vs-different-extension is explicitly checked by ID equality:

toolkit/mozapps/extensions/internal/XPIInstall.sys.mjs:1636-1639
    if (this.addon.id != this.existingAddon.id) {
      ... "Refusing to upgrade addon ${this.existingAddon.id} to different ID ${this.addon.id}"
    }

XPIDatabase (and the UUID_MAP_PREF pref that backs the origin UUID map) are
both profile-scoped resources, matching Chromium's per-profile model.

### WebKit: uniqueness is enforced on the origin host, per WebExtensionController

Source/WebKit/UIProcess/Extensions/Cocoa/WebExtensionControllerCocoa.mm:286-296
    if (!m_extensionContexts.add(extensionContext)) {
      ... return makeUnexpected(extensionContext.createError(WebExtensionContext::Error::AlreadyLoaded));
    }
    if (!m_extensionContextBaseURLMap.add(extensionContext.baseURL().protocolHostAndPort(), extensionContext)) {
      ... return makeUnexpected(extensionContext.createError(WebExtensionContext::Error::BaseURLAlreadyInUse));
    }

This is the one engine where the collision check is explicitly on the origin
host (protocolHostAndPort()), not on the identifier per se - though by
default the host equals the identifier, so in the default case this is
equivalent to enforcing ID uniqueness. The scope is one
WebExtensionController (the object an embedding app creates to host a set
of extension contexts, roughly the WebKit analog of a profile).

## 6. Exposure to extension code and to web pages

### Chromium
- To extension code: chrome.runtime.id, described in
  extensions/common/api/runtime.json:312-314 ("id": {"type": "string",
  "description": "The ID of the extension/app."}), a top-level property of
  the runtime namespace auto-populated per calling extension context.
- To web pages: runtime.connect/runtime.sendMessage take an explicit
  extensionId string parameter for cross-extension or extension-from-page
  connections (extensions/common/api/runtime.json:487,535), and any page
  that already knows or guesses an ID can attempt to load a
  chrome-extension://<id>/... resource URL (subject to
  web_accessible_resources allowlisting) - the ID is therefore directly
  visible in that URL when such a request succeeds or is attempted.

### Gecko
- To extension code: browser.runtime.id returns extension.id, the
  manifest-authored ID (toolkit/components/extensions/child/ext-runtime.js:133).
- To web pages: the ID is used the same way as Chromium's for
  externally_connectable-style messaging (an ID string is required to
  target an extension), but the origin host a page would observe
  (moz-extension://<uuid>/...) is the anti-fingerprinting UUID, not the ID -
  so a web page cannot learn the ID merely by observing or probing the
  extension's resource origin (this is the explicit rationale quoted in
  point 4 above).

### WebKit
- To extension code: browser.runtime.id returns uniqueIdentifier()
  (Source/WebKit/WebProcess/Extensions/API/Cocoa/WebExtensionAPIRuntimeCocoa.mm:186-190).
- To web pages: since the origin host defaults to the identifier itself
  (webkit-extension://<uniqueIdentifier>/), a page that can reach that
  origin (e.g. via an allowed web-accessible resource) directly observes the
  identifier as the host - WebKit has no separate anti-fingerprinting host
  indirection comparable to Gecko's UUIDMap. Whether that identifier is
  guessable/stable across launches depends entirely on the embedding app's
  choice, per point 3.

## Resolved points, formerly open

- **Store-side ID-uniqueness enforcement: not in open source.** Chrome Web
  Store, addons.mozilla.org, and App Store Connect are server-side
  distribution backends; none of their code is checked into the Chromium,
  Gecko, or WebKit trees read for this task (these are browser-source
  checkouts, not store-backend repositories, so there is nothing in them to
  find). Only the local/profile-scoped derivation and collision-avoidance
  mechanisms documented above are backed by source read for this task.
  Classification: not in open source.

- **Whether WebKit's own engine generates and persists a default
  uniqueIdentifier, versus Safari's specific choice of identifier and
  scheme: these are two different questions with two different answers.**
  WebKit's own default-generation behavior is fully resolved from source
  (see point 3 above): a fresh random UUIDv4 is generated every time a
  `WebExtensionContext` is constructed
  (`Source/WebKit/UIProcess/Extensions/WebExtensionContext.h:1095`), it is
  never itself persisted to disk by the engine, and it is stable across
  launches only if the embedding application calls `setUniqueIdentifier`
  with a value the application generates and persists itself before each
  `load()` (`Source/WebKit/UIProcess/Extensions/WebExtensionContext.cpp:154-165`,
  guarded by `ASSERT(!isLoaded())`). That much is resolved and open-source.

  Scheme substitution is also resolved as a *mechanism*, open-source:
  `webkit-extension` is the engine's own built-in default scheme, held in a
  static set (`WebExtensionMatchPattern::extensionSchemes()`/
  `validSchemes()`/`supportedSchemes()`,
  `Source/WebKit/UIProcess/Extensions/WebExtensionMatchPattern.cpp:50-64`).
  A second scheme, such as Safari's `safari-web-extension`, is added to
  those same sets only by an explicit runtime call from the embedding app
  to `+[WKWebExtensionMatchPattern registerCustomURLScheme:]`
  (`Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionMatchPattern.h:83`,
  implemented at
  `Source/WebKit/UIProcess/API/Cocoa/WKWebExtensionMatchPattern.mm:54-59`
  calling `WebExtensionMatchPattern::registerCustomURLScheme`,
  `WebExtensionMatchPattern.cpp:94-103`). The header comment states this
  plainly: "This method should be used to register any custom URL schemes
  used by the app for the extension base URLs, other than
  `webkit-extension`" (`WKWebExtensionMatchPattern.h:77-82`). No call site
  for `registerCustomURLScheme:` exists anywhere in the WebKit tree itself
  (grepped the whole tree; the only occurrences are the declaration and
  definition) -- it exists to be called by an embedding app, and is never
  invoked from within WebKit's own code.

  What remains genuinely closed: whether Safari specifically calls
  `setUniqueIdentifier`/`registerCustomURLScheme:` (rather than relying on
  WebKit's own UUID/`webkit-extension` defaults), what concrete identifier
  and scheme string it passes, and whether/how it persists that value
  across launches on disk. That is Safari application code, not present in
  the WebKit tree read here. Classification: mechanism resolved
  (open-source); Safari's specific runtime choice is not in open source.

- **Chromium's `chrome.runtime.id` bindings-layer path: resolved,
  traced end to end.** `chrome.runtime.id` is registered as a V8 "native
  data property" (an accessor, not a plain value) by
  `RuntimeHooksDelegate::InitializeTemplate`:

      object_template->SetNativeDataProperty(gin::StringToSymbol(isolate, "id"),
                                             &GetExtensionId, &EmptySetter);

  (`extensions/renderer/api/runtime_hooks_delegate.cc:469-470`). The getter,
  `GetExtensionId` (`runtime_hooks_delegate.cc:56-70`), resolves the calling
  `ScriptContext` from the V8 property access's creation context via
  `GetScriptContextFromV8Context(context)`, then returns
  `script_context->extension()->id()` -- the same `Extension::id()`
  accessor already cited in point 1 above -- converted to a V8 string with
  `gin::StringToSymbol`. So the full chain is: schema declares `id` as a
  string property with no static `"value"`
  (`extensions/common/api/runtime.json:312-315`) -> the runtime API's hooks
  delegate installs a native accessor for it at template-initialization
  time -> the accessor reads the per-context `Extension` object's `id()`
  at access time, not at template-creation time, so each extension's own
  script context sees its own ID.

  A sibling accessor at the same call site, `dynamicId`
  (`runtime_hooks_delegate.cc:472-473,74-87`), reads `extension()->guid()`
  instead -- this is the same per-install random `ExtensionGuid` already
  documented in point 4 above (the `use_dynamic_url` mechanism), confirming
  from the renderer side that it is a deliberately separate value from
  `id()`, not an alternate name for it. Classification: resolved.

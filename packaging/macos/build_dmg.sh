#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/build/macos"
DIST="$ROOT/dist"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VERSION="$($PYTHON_BIN -c 'import sys;sys.path.insert(0,"src");import crossaudit;print(crossaudit.__version__)' 2>/dev/null)"
BUILD_NUMBER="${CROSSAUDIT_BUILD_NUMBER:-1}"
SIGN_IDENTITY="${CROSSAUDIT_CODESIGN_IDENTITY:--}"
NOTARY_PROFILE="${CROSSAUDIT_NOTARY_PROFILE:-}"
PUBLIC_RELEASE="${CROSSAUDIT_PUBLIC_RELEASE:-0}"
ARCH="$(uname -m)"
CODEX_VERSION="0.146.0"
CODEX_TAG="rust-v$CODEX_VERSION"
CODEX_ARCHIVE="$BUILD/codex-aarch64-apple-darwin-$CODEX_VERSION.tar.gz"
CODEX_LICENSE="$BUILD/OpenAI-Codex-LICENSE-$CODEX_VERSION"
CODEX_SHA256="2750132d300e64f1dbffb95e3d913fd9c9dc7812bc8e1bce5c61357248b7929e"
CODEX_LICENSE_SHA256="d17f227e4df5da1600391338865ce0f3055211760a36688f816941d58232d8dc"

if [[ "$ARCH" != "arm64" ]]; then
  echo "This build currently targets Apple Silicon; found $ARCH." >&2
  exit 2
fi

if [[ "$PUBLIC_RELEASE" == "1" && "$SIGN_IDENTITY" == "-" ]]; then
  echo "A public release requires CROSSAUDIT_CODESIGN_IDENTITY." >&2
  exit 7
fi
if [[ "$PUBLIC_RELEASE" == "1" && -z "$NOTARY_PROFILE" ]]; then
  echo "A public release requires CROSSAUDIT_NOTARY_PROFILE." >&2
  exit 8
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/crossaudit-v4-release.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/CrossAudit.app"
DMG_ROOT="$STAGE/dmg-root"

mkdir -p "$BUILD" "$DIST"
# D47: retain the last shipped artifact before overwriting it.
# Artifact-to-artifact comparison is the only way to answer "did a late
# boundary catch a path that used to work", and it has found real defects
# three times. Keeping exactly one previous build makes that repeatable
# instead of depending on an old bundle happening to still be on disk.
PREV="$DIST/previous"
PREV_DMG="$DIST/CrossAudit-$VERSION-arm64.dmg"
if [[ -f "$PREV_DMG" ]]; then
  rm -rf "$PREV"
  mkdir -p "$PREV"
  ditto "$PREV_DMG" "$PREV/$(basename "$PREV_DMG")"
  [[ -f "$PREV_DMG.sha256" ]] && ditto "$PREV_DMG.sha256" "$PREV/"
  # The .app a reviewer drives must come OUT OF THE PREVIOUS DMG. $APP at
  # this point is the build we just made, so copying it here would retain
  # the new artifact under the name of the old one -- worse than retaining
  # nothing, because it would look like evidence.
  PREV_MNT="$(mktemp -d)"
  if hdiutil attach -quiet -nobrowse -readonly -mountpoint "$PREV_MNT" "$PREV/$(basename "$PREV_DMG")"; then
    ditto "$PREV_MNT/CrossAudit.app" "$PREV/CrossAudit.app"
    hdiutil detach -quiet "$PREV_MNT"
  else
    echo "warning: could not mount the previous DMG; retained the disk image only" >&2
  fi
  rmdir "$PREV_MNT" 2>/dev/null || true
  date -u "+%Y-%m-%dT%H:%M:%SZ" > "$PREV/retained-at.txt"
  echo "retained previous artifact in $PREV"
fi

rm -rf "$BUILD/pyinstaller-dist" "$BUILD/pyinstaller-work" "$BUILD/icon.iconset" \
       "$DIST/CrossAudit.app" "$DIST/CrossAudit-$VERSION-arm64.dmg"

if [[ ! -x "$BUILD/venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$BUILD/venv"
fi
"$BUILD/venv/bin/python" -m pip install --disable-pip-version-check -q --upgrade pip wheel
"$BUILD/venv/bin/python" -m pip install --disable-pip-version-check -q "pyinstaller>=6.15" "$ROOT"

cd "$ROOT"
"$BUILD/venv/bin/python" packaging/macos/build_identity.py
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean \
  --distpath "$BUILD/pyinstaller-dist" --workpath "$BUILD/pyinstaller-work" \
  packaging/macos/CrossAuditCore.spec

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/core" \
         "$APP/Contents/Resources/bin" "$APP/Contents/Resources/licenses"
xcrun swiftc -O -target arm64-apple-macos13.0 \
  -framework AppKit -framework WebKit \
  packaging/macos/CrossAuditApp.swift -o "$APP/Contents/MacOS/CrossAudit"
ditto "$BUILD/pyinstaller-dist/CrossAuditCore" "$APP/Contents/Resources/core"

GH_BIN="$(command -v gh || true)"
if [[ -z "$GH_BIN" ]]; then
  echo "GitHub CLI is required to build the complete app bundle." >&2
  exit 3
fi
cp "$GH_BIN" "$APP/Contents/Resources/bin/gh"
chmod 755 "$APP/Contents/Resources/bin/gh"

# ChatGPT subscription access is provided only through OpenAI's official,
# open-source Codex runtime. Pin both the release and its digest so packaging
# cannot silently absorb a changed binary. The runtime, not CrossAudit, owns
# browser login, refresh tokens, and account storage.
if [[ ! -f "$CODEX_ARCHIVE" ]] || \
   [[ "$(shasum -a 256 "$CODEX_ARCHIVE" | awk '{print $1}')" != "$CODEX_SHA256" ]]; then
  curl -fL --retry 3 -o "$CODEX_ARCHIVE" \
    "https://github.com/openai/codex/releases/download/$CODEX_TAG/codex-aarch64-apple-darwin.tar.gz"
fi
if [[ "$(shasum -a 256 "$CODEX_ARCHIVE" | awk '{print $1}')" != "$CODEX_SHA256" ]]; then
  echo "The pinned OpenAI Codex runtime failed its SHA-256 check." >&2
  exit 4
fi
tar -xzf "$CODEX_ARCHIVE" -C "$STAGE"
CODEX_BIN="$STAGE/codex-aarch64-apple-darwin"
if [[ ! -x "$CODEX_BIN" ]]; then
  echo "The pinned OpenAI Codex archive did not contain the expected executable." >&2
  exit 5
fi
cp "$CODEX_BIN" "$APP/Contents/Resources/bin/codex"
chmod 755 "$APP/Contents/Resources/bin/codex"
if [[ ! -f "$CODEX_LICENSE" ]] || \
   [[ "$(shasum -a 256 "$CODEX_LICENSE" | awk '{print $1}')" != "$CODEX_LICENSE_SHA256" ]]; then
  INSTALLED_CODEX_LICENSE="/Applications/CrossAudit.app/Contents/Resources/licenses/OpenAI-Codex-LICENSE"
  if [[ -f "$INSTALLED_CODEX_LICENSE" ]] && \
     [[ "$(shasum -a 256 "$INSTALLED_CODEX_LICENSE" | awk '{print $1}')" == "$CODEX_LICENSE_SHA256" ]]; then
    cp "$INSTALLED_CODEX_LICENSE" "$CODEX_LICENSE"
  else
    curl -fsSL --retry 3 -o "$CODEX_LICENSE" \
      "https://raw.githubusercontent.com/openai/codex/$CODEX_TAG/LICENSE"
  fi
fi
if [[ "$(shasum -a 256 "$CODEX_LICENSE" | awk '{print $1}')" != "$CODEX_LICENSE_SHA256" ]]; then
  echo "The pinned OpenAI Codex license failed its SHA-256 check." >&2
  exit 6
fi
cp "$CODEX_LICENSE" "$APP/Contents/Resources/licenses/OpenAI-Codex-LICENSE"
cp packaging/macos/GITHUB_CLI_LICENSE "$APP/Contents/Resources/licenses/GitHub-CLI-LICENSE"
cp LICENSE "$APP/Contents/Resources/licenses/CrossAudit-LICENSE"

sed -e "s/@VERSION@/$VERSION/g" -e "s/@BUILD@/$BUILD_NUMBER/g" \
  packaging/macos/Info.plist.in > "$APP/Contents/Info.plist"
xcrun swift packaging/macos/make_icon.swift "$BUILD/icon.iconset"
iconutil -c icns "$BUILD/icon.iconset" -o "$APP/Contents/Resources/AppIcon.icns"

# Run the exact frozen core before it is signed. This validates bundled imports,
# controller bootstrap, PDF/DOCX round-trips, and loopback-token enforcement.
SELF_TEST="$($APP/Contents/Resources/core/CrossAuditCore --self-test)"
SELF_TEST_JSON="$SELF_TEST" "$PYTHON_BIN" - <<'PY'
import json, os
result = json.loads(os.environ["SELF_TEST_JSON"])
if result.get("ok") is not True or result.get("loopback_token_enforced") is not True:
    raise SystemExit("frozen runtime self-test did not pass")
if not all(result.get("documents", {}).get(kind, {}).get("valid")
           for kind in ("pdf", "docx")):
    raise SystemExit("frozen document round-trip did not pass")
if int(result.get("tls", {}).get("trusted_certificate_authorities", 0)) < 1:
    raise SystemExit("frozen runtime has no trusted TLS certificate authorities")
digest = str(result.get("dcl_source_sha256", ""))
if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
    raise SystemExit("frozen runtime has no deterministic-layer identity")
PY

# Finder tags, quarantine state, and AppleDouble/resource-fork metadata are not
# application resources. Copying a source tree from a user workspace can attach
# them to nested files, and strict code signing must fail rather than seal that
# machine-local detritus into a release.
xattr -cr "$APP"
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --deep --sign - --options runtime --timestamp=none "$APP"
else
  codesign --force --deep --sign "$SIGN_IDENTITY" --options runtime --timestamp "$APP"
fi
codesign --verify --deep --strict --verbose=2 "$APP"
plutil -lint "$APP/Contents/Info.plist"

mkdir -p "$DMG_ROOT"
ditto "$APP" "$DMG_ROOT/CrossAudit.app"
ln -s /Applications "$DMG_ROOT/Applications"
# D40. The DMG deliberately installs nothing onto PATH (D31 part 2, on consent
# grounds). That leaves one thing a person cannot find out for themselves: if
# they ever `pip install crossaudit`, that older program stays earlier on PATH
# and answers when they type `crossaudit`. We cannot fix that from inside the
# app — in that state our CLI never runs — so we say it here, where the person
# is at the moment they install.
cat > "$DMG_ROOT/About the crossaudit command.txt" <<'DMGNOTE'
CrossAudit is a Mac app. Dragging it to Applications does not add a `crossaudit`
command to your terminal, and that is deliberate: a tool appears on your PATH
only through an action you take yourself.

If you have ever run `pip install crossaudit`, that installation is still on
your PATH and will answer when you type `crossaudit` — even after installing
this app, and even if it is much older. The two are separate programs.

To see which one answers:

    which crossaudit
    crossaudit --version

The app's own command line lives inside the bundle:

    /Applications/CrossAudit.app/Contents/Resources/core/CrossAuditCore --version

The app also reports this: open it and look at "The `crossaudit` command" in
its readiness list. It names both programs, and it never runs the other one to
ask its version.
DMGNOTE
# The first thing macOS does with an ad-hoc signed app is refuse to open it.
# Nothing inside the app can say so — it has not run yet — so the sentence sits
# in the DMG window, beside the app, in both languages, before the person
# meets the dialog. Ships whether or not the build was notarized: a notarized
# build never shows the dialog and the note costs nothing.
cat > "$DMG_ROOT/如何打开 · How to open.txt" <<'OPENNOTE'
How to open CrossAudit

macOS may say the app can't be verified — right-click CrossAudit.app → Open
→ Open. This happens once.

如何打开 CrossAudit

macOS 可能提示无法验证此应用。右键点击 CrossAudit.app → 打开 → 打开。
只需这样做一次。
OPENNOTE
hdiutil create -quiet -volname "CrossAudit $VERSION" -srcfolder "$DMG_ROOT" \
  -ov -format UDZO "$DIST/CrossAudit-$VERSION-arm64.dmg"
if [[ -n "$NOTARY_PROFILE" ]]; then
  xcrun notarytool submit "$DIST/CrossAudit-$VERSION-arm64.dmg" \
    --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DIST/CrossAudit-$VERSION-arm64.dmg"
fi
hdiutil verify "$DIST/CrossAudit-$VERSION-arm64.dmg"
(cd "$DIST" && shasum -a 256 "CrossAudit-$VERSION-arm64.dmg" > \
  "CrossAudit-$VERSION-arm64.dmg.sha256")

packaging/macos/verify_dmg.sh "$DIST/CrossAudit-$VERSION-arm64.dmg" "$VERSION"

echo
echo "Built $DIST/CrossAudit-$VERSION-arm64.dmg"

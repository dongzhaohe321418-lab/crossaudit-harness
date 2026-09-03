# CrossAudit website

The public product site for CrossAudit. It explains the independent audit loop,
keeps advanced capabilities progressively disclosed, and resolves the current
macOS installer and checksum from the official GitHub Releases API.

Production: <https://crossaudit-v4.vercel.app>

## Production notes

- **Release source.** Every download control reads
  `https://api.github.com/repos/dongzhaohe321418-lab/crossaudit-harness/releases/latest`
  in the browser and links the DMG and `.sha256` assets it finds there. If the
  API is unavailable or rate-limited, every control falls back to the
  repository's official `releases/latest` URL, never to a third-party mirror.
- **Fallback version.** `FALLBACK_RELEASE.tag_name` in
  `app/CrossAuditLanding.tsx` and `version` in `package.json` are what the page
  shows before (or without) a GitHub answer. Bump both with every product
  release; `tests/rendered-html.test.mjs` pins the release links.
- **Installer wording.** The DMG is ad-hoc signed and not Apple-notarized, so
  the page says plainly that macOS asks for right-click, then Open, on the
  first launch, and states the requirement: Apple Silicon, macOS 13 or later.
  Keep that wording until the build is notarized.
- **Screenshots.** `public/crossaudit-workspace*.png` and
  `public/crossaudit-audit*.png` are captures of the real 4.16.0 console showing
  the credential-free local demo project (the "sample" banner is deliberate:
  no model ran). Regenerate with `scripts/shoot-console.mjs` against a running
  core, then downscale with `sips -Z 1600` and `sips -Z 960`; the page code
  declares 2704x1824 and never needs to change. `public/og.png` is the static
  brand image for link previews.
- **Domain.** `metadataBase` in `app/layout.tsx` stays
  `https://crossaudit-v4.vercel.app`; the source repository moved to
  `dongzhaohe321418-lab/crossaudit-harness` but the site domain did not.
- **Copy parity.** Every string exists in English and Simplified Chinese in
  the `copy` table; a claim added to one language is added to the other in
  the same change. The component must not contain em or en dashes (the test
  refuses them); use a comma, a colon, or an arrow.

## Local development

```bash
npm ci
npm run dev
```

`package.json` declares Node 24. A newer Node runs the toolchain as well (the
engine field is advisory); an older one does not.

## Building

Two independent build paths exist; both must work from a clean clone:

- `npm run build` — vinext + Cloudflare Worker runtime (what `npm test`
  serves). It loads `vite.config.ts`, which needs the Sites packaging plugin
  in `lib/sites-vite-plugin.ts`. The plugin lives in `lib/` and not the
  starter's original `build/` directory because the repository root
  `.gitignore` ignores `build/` — the original location was never committed,
  which broke every fresh checkout.
- `npm run build:vercel` — plain `next build` for the Vercel runtime. It
  never loads `vite.config.ts`, so it does not need the plugin.

## Validation

```bash
npm run lint
npm test
npm run build:vercel
```

The production build targets the Sites/Cloudflare Worker runtime declared in
`.openai/hosting.json`. The separate `build:vercel` target validates the same
source with the standard Next.js production runtime before Vercel deployment.
No credentials are needed to build or browse the site.

## Vercel release gate

Only deploy after all three validation commands pass. The local `.vercel`
binding is intentionally ignored by Git and connects this folder to the user's
Vercel project without storing account credentials in the source tree. A fresh
clone has no binding: run `npx vercel link` once, signed in to the account that
owns `crossaudit-v4`, before the first `release:vercel`.

```bash
npm run release:vercel
```

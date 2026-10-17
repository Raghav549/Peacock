# PEACOCK website

The website application is written in **`site.pac`**, not Python, JavaScript,
TypeScript or a UI framework. `site.pac` defines twelve page functions, a small
reusable `UiNode` component tree, route/navigation state, HTML escaping, a
semantic HTML renderer and responsive CSS. The pages embed `.pac` source files
read from `examples/` at build time.

There is no user-file module/import system yet, so all twelve page definitions
are compiled together in this one genuine PEACOCK compilation unit. The Python
bootstrap compiles and runs it. `fs` is the explicit host boundary used to read
examples/logo data and write the generated site. The browser performs ordinary
HTML/CSS layout and presentation. The output contains HTML, CSS and the existing
SVG logo; **it contains no JavaScript bundle or third-party frontend framework**.

## Build

From the repository root with Python 3.11+:

```bash
./bin/peacock check website/site.pac
./bin/peacock build website/site.pac -o /tmp/peacock-website.pkb
./bin/peacock run website/site.pac \
  --grant fs --root . --max-steps 10000000 -- website/dist
```

The website generator currently needs the explicit 10,000,000-step budget
because it renders twelve pages, computes thin-film iridescence and WCAG
contrast telemetry, renders `assets/chromatic-3d-preview.png` via the PEACOCK
2D/3D software rasteriser, computes SHA-256 digests of embedded `.pac` sources,
and escapes source text inside the reference VM. `fs` must be granted by the
host and declared in `main`; the output remains confined to the selected
sandbox root.

## Vercel deployment configuration

The previous Vercel `404: NOT_FOUND` failure on
`https://peacock-website-eight.vercel.app` occurred because the repository root
had no `vercel.json`, no root `index.html`, and `website/dist/` was excluded by
`.gitignore`, causing Vercel to perform a 2-second no-build static deployment of
the repo root with zero HTML files.

This is fixed by:

1. `vercel.json` at the repository root declaring `buildCommand: ""`, `outputDirectory: "website/dist"`, and `cleanUrls: true` (empirically verified via Vercel commit statuses: running `python3 ./bin/peacock` inside Vercel's Node build container failed in `dpl_BGRmnyu8uyhFe6h5Nmw97WAGbEcr` because the bootstrap requires Python 3.11+, whereas serving pre-built `outputDirectory: "website/dist"` succeeded in `dpl_JC57G3jP4G3qBVVZ8cbdNgm94A9d`);
2. fixing `.gitignore` (where both `website/dist/` and unanchored `dist/` previously excluded `website/dist/`), tracking the verified `website/dist/` output built by `./bin/peacock run website/site.pac`, and enforcing byte-exact parity between `website/site.pac` and `website/dist/` in `tests/integration/test_website.py` and GitHub Actions CI.

Serve the exported files locally:

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory website/dist
```

The optional Python standard-library HTTP server is only a static-file host;
it does not generate application pages. In an Arena/container preview, bind to
`0.0.0.0` instead of `127.0.0.1`.

## Routes and interactions

The export contains twelve independent routes: Home, Language, Compiler, AI
Engine, Frontend Studio, Docs, Examples, Research, Roadmap, Security, Get Started
and Community. Every page has the same navigation, and the current route is
marked with `aria-current="page"`. The Examples page offers keyboard-accessible
category filter links that jump to language, AI and graphics examples. Code is
selectable text so the browser's normal copy command can be used. Native
`details`/`summary`, link navigation and responsive overflow navigation need no
script.

The design includes responsive breakpoints, visible keyboard focus, a skip link,
semantic landmarks/headings, labelled navigation, image alternative text and a
`prefers-reduced-motion` fallback. The integration test builds the app through
the real PEACOCK CLI, verifies all twelve routes, checks internal paths and
fragments, checks source examples and accessibility markers, and checks the
responsive/reduced-motion CSS. These are source-level checks; no browser-based
visual regression suite has been run.

## Honest boundary

This is a working PEACOCK-authored **static web export**, not a general
interactive UI runtime and not the existing `WebBackend` PNG-frame viewer. Its
component tree, page content, route selection and renderer are PEACOCK code; the
output is standard browser HTML/CSS. There is no client-side search, live AI demo,
web UI event loop, or JavaScript. General-purpose UI components, dynamic state,
input, text shaping and 3D remain future frontend work. Download links, release
assets, package-registry claims and community metrics are not invented.

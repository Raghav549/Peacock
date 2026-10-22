# PEACOCK website

The website application is written in **`site.सूत्र`**, not Python, JavaScript,
TypeScript or a UI framework. `site.सूत्र` defines twelve page functions, a small
reusable `UiNode` component tree, route/navigation state, HTML escaping, a
semantic HTML renderer and responsive CSS. The pages embed `.सूत्र` source files
read from `examples/` at build time.

There is no user-file module/import system yet, so all twelve page definitions
are compiled together in this one genuine PEACOCK compilation unit. The Python
bootstrap compiles and runs it. `सञ्चय` is the explicit host boundary used to read
examples/logo data and write the generated site. The browser performs ordinary
HTML/CSS layout and presentation. The output contains HTML, CSS and the existing
SVG logo; **it contains no JavaScript bundle or third-party frontend framework**.

## Build

From the repository root with Python 3.11+:

```bash
./bin/peacock check website/site.सूत्र
./bin/peacock build website/site.सूत्र -o /tmp/peacock-website.बीज
./bin/peacock run website/site.सूत्र \
  --grant सञ्चय --root . --max-steps 10000000 -- website/dist
```

The website generator currently needs the explicit 10,000,000-step budget
because it renders twelve pages and escapes the real example source text inside
the reference VM. `सञ्चय` must be granted by the host and declared in `main`; the
output remains confined to the selected sandbox root. `website/dist/` is a
build artifact and is ignored by Git.

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

---
name: fls-mkdocs-site
description: How the formal-ledger-specifications mkdocs site is built and how to change it safely — which module pages exist (import closure of src/Ledger.lagda.md), strict-mode link rules, nav/tab ordering, local preview paths (dist vs result), and a mini-repro technique for theme-behavior questions. Use when editing mkdocs.yml, adding pages or internal links, or debugging the docs site.
---

# The fls docs site

## How it builds
`fls-shake mkdocs` (or `nix build .#mkdocs`): `agda --fls src/Ledger.lagda.md`
emits one `<Dotted.Module.Name>.md` per module in the IMPORT CLOSURE into
`_build/mkdocs/docs/`; then `build-tools/static/mkdocs/**` (mkdocs.yml, static
pages, the generated dashboard/issues view) is copied in and `README.md`
becomes `index.md`; then `mkdocs build -s` (STRICT) renders into `dist/mkdocs`.

## Page existence = closure membership, not nav membership
A module page exists iff the module is reachable from `src/Ledger.lagda.md`
via imports — aggregator modules (`X/Properties.lagda.md`) re-export the
property modules, which is what pulls them in. Literate modules imported
nowhere get NO page (as of 2026-08: `Interface.TypeClasses`,
`Ledger.Dijkstra.Specification.Computational`). Before adding a nav entry or
internal link, check reachability: BFS over `^\s*(open\s+)?import` lines
across `src/` and `src-lib-exts/` starting from `Ledger`.

## Strict mode rules (`mkdocs build -s`)
- A link to a nonexistent page = BUILD FAILURE. Never link a `planned`
  module (its file is not on the branch).
- A page present in the docs dir but absent from nav = INFO only; it builds
  and is reachable by URL.
- External URLs are not validated.

## Links and URLs
`use_directory_urls: false` ⇒ pages are `<name>.html` (e.g.
`/ledger-properties-dashboard.html`). All generated module pages and the
dashboard share one directory, so internal links are simply
`<Dotted.Module.Name>.md` — mkdocs rewrites them to `.html`.

## Tabs = top-level nav order, nothing else
mkdocs-material renders one tab per TOP-LEVEL nav item — pages and sections
alike, strictly in nav order (verified against 9.7.0: the tabs partial loops
`nav.items` with no hoisting). If a nav edit "has no effect", the artifact is
stale: `result/` is an immutable nix-store snapshot (rerun `nix build`);
`fls-shake mkdocs` writes to `dist/mkdocs` (not `result/`); otherwise
hard-refresh the browser (the tab bar is baked into every page).

## Theme-behavior questions
Do not guess or trust memory: read the installed theme's templates
(`python3 -c "import material,os; print(os.path.dirname(material.__file__))"`
→ `templates/partials/`), and/or build a six-file mini site in the scratchpad
with the same theme + features and inspect the emitted HTML.

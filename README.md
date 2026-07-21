# logos

Refreshable brand-logo assets for decks (connectors, cloud, BI, comms, customers).
Served over jsDelivr CDN — hotlinks reliably in-browser and in Print→PDF.

## Usage
```
https://cdn.jsdelivr.net/gh/dataruleseverythingaroundme/logos@main/<filename>
```
Naming: `<category>-<type>-<Name>.<ext>` — `type` defaults to `logo`. Categories: `datasource`, `bi`, `cloud`, `comms`, `customer`, `output`, `brand`.
Product connector UI icons use `type` = `icon`, e.g. `datasource-icon-<name>.<ext>`, `brand-icon-<Name>.<ext>`.
`brand` covers first-party Tellius/Kaiya marks (e.g. `brand-logo-Tellius-T-purple.png`, `brand-icon-Kaiya-chat.png`) — committed directly, no external refresh source.

See `logos.manifest.json` for the source-of-record mapping (Wikidata/Commons refresh).

## Mirror layer — the long tail (`mirror.manifest.json`)
`mirror.manifest.json` is a **reference-only** index of the two public fallback libraries below, keyed under this repo's convention. **No image bytes are stored here** — every entry's `url` points at an upstream jsDelivr file. It exists so a lookup ("do we have a Databricks logo?") covers ~6,400 more brands without vendoring them.

- Convention: mirror entries use category `lib`, type `logo`, and the upstream slug verbatim — `lib-logo-<slug>` (e.g. `lib-logo-looker`, `lib-logo-adobe`).
- Each entry carries a ready-to-use `url`. theSVG entries also list `variants` (`default`, `mono`, `wordmark`, `dark`, `light`, …); swap `/default.svg` → `/<variant>.svg`. gilbarbara entries list `files`.
- **Precedence:** a curated, categorized file in this repo (e.g. `bi-logo-Looker.svg`) always wins over the `lib-` mirror entry for the same brand. On a slug collision between the two libraries, theSVG wins (multi-variant); gilbarbara fills gaps.
- Regenerate with `python3 refresh_mirror.py` to track upstream renames/additions.

### Resolving a logo (curated → mirror → miss)
1. Look for a curated file in this repo by category/name.
2. Else look up `lib-logo-<slug>` in `mirror.manifest.json` and use its `url`.
3. Else it's genuinely missing — add it (see naming above) or source it.

## Fallback libraries (indexed by the mirror, not vendored here)
- theSVG — `https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/{variant}.svg`
- gilbarbara/logos — `https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{name}.svg`

Brand marks are the IP of their respective owners (referential use). The mirror stores only names and URLs, never the marks themselves.

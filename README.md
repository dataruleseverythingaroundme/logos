# logos

Refreshable brand-logo assets for decks (connectors, cloud, BI, comms, customers).
Served over jsDelivr CDN — hotlinks reliably in-browser and in Print→PDF.

## Usage
```
https://cdn.jsdelivr.net/gh/dataruleseverythingaroundme/logos@main/<filename>
```
Naming: `<type>-<category>-<Name>.<ext>` — `type` is `logo` (default) or `icon`. Categories: `data`, `bi`, `cloud`, `comms`, `firm`, `output`, `ai`, `Tellius`.
Product connector UI icons use `type` = `icon`, e.g. `icon-data-<name>.<ext>` (slugs kept lowercase, e.g. `icon-data-hive_jdbc.png`).
First-party marks: Tellius corporate → `ai` (e.g. `logo-ai-Tellius-T_Purple.png`); Tellius products → `Tellius` (e.g. `logo-Tellius-Kaiya-chat.png`) — committed directly, no external refresh source.

See `logos.manifest.json` for the source-of-record mapping (Wikidata/Commons refresh).

## Mirror layer — the long tail (`mirror.manifest.json`)
`mirror.manifest.json` is a **reference-only** index of the two public fallback libraries below, keyed under this repo's convention. **No image bytes are stored here** — every entry's `url` points at an upstream jsDelivr file. It exists so a lookup ("do we have a Databricks logo?") covers ~6,400 more brands without vendoring them.

- Convention: mirror entries use type `logo`, category `lib`, and the upstream slug verbatim — `logo-lib-<slug>` (e.g. `logo-lib-looker`, `logo-lib-adobe`).
- Each entry carries a ready-to-use `url`. theSVG entries also list `variants` (`default`, `mono`, `wordmark`, `dark`, `light`, …); swap `/default.svg` → `/<variant>.svg`. gilbarbara entries list `files`.
- **Precedence:** a curated, categorized file in this repo (e.g. `logo-bi-Looker.svg`) always wins over the `logo-lib-` mirror entry for the same brand. On a slug collision between the two libraries, theSVG wins (multi-variant); gilbarbara fills gaps.
- Regenerate with `python3 refresh_mirror.py` to track upstream renames/additions.

### Resolving a logo (curated → mirror → miss)
1. Look for a curated file in this repo by category/name.
2. Else look up `logo-lib-<slug>` in `mirror.manifest.json` and use its `url`.
3. Else it's genuinely missing — add it (see naming above) or source it.

## Fallback libraries (indexed by the mirror, not vendored here)
- theSVG — `https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/{variant}.svg`
- gilbarbara/logos — `https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{name}.svg`

Brand marks are the IP of their respective owners (referential use). The mirror stores only names and URLs, never the marks themselves.

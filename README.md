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

## Fallback libraries (not vendored here)
- theSVG — `https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/{variant}.svg`
- gilbarbara/logos — `https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{name}.svg`

Brand marks are the IP of their respective owners (referential use).

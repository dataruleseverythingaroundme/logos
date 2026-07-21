#!/usr/bin/env python3
"""Regenerate mirror.manifest.json — a reference-only index of the two public
fallback logo libraries (theSVG + gilbarbara), keyed under this repo's naming
convention. No image bytes are copied; every entry resolves to an upstream
jsDelivr URL. Re-run any time to track upstream renames/additions.

Convention: mirror entries use category `lib`, type `logo`, and the upstream
slug verbatim as the Name -> `lib-logo-<slug>`. Curated first-party/deck files
in this repo always win over a `lib-` mirror entry for the same brand.

Priority on slug collisions: theSVG first (multi-variant, actively maintained),
then gilbarbara for anything theSVG lacks.
"""
import json
import urllib.request

GILBARBARA_INDEX = "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos.json"
THESVG_TREE = "https://data.jsdelivr.com/v1/packages/gh/glincker/thesvg@main"

GB_FILE_URL = "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{file}"
TS_FILE_URL = "https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/{variant}.svg"


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _find(nodes, name):
    for n in nodes:
        if n["name"] == name:
            return n
    return None


def thesvg_entries():
    tree = fetch_json(THESVG_TREE)
    public = _find(tree["files"], "public")
    icons = _find(public["files"], "icons")
    out = []
    for brand in icons["files"]:
        if brand.get("type") != "directory":
            continue
        slug = brand["name"]
        variants = sorted(
            f["name"][:-4] for f in brand.get("files", []) if f["name"].endswith(".svg")
        )
        if not variants:
            continue
        default = "default" if "default" in variants else variants[0]
        out.append({
            "name": f"lib-logo-{slug}",
            "source": "thesvg",
            "slug": slug,
            "url": TS_FILE_URL.format(slug=slug, variant=default),
            "variants": variants,
        })
    return out


def gilbarbara_entries():
    data = fetch_json(GILBARBARA_INDEX)
    out = []
    for e in data:
        slug = e["shortname"]
        files = e.get("files", [])
        if not files:
            continue
        primary = next((f for f in files if f == f"{slug}.svg"), min(files, key=len))
        out.append({
            "name": f"lib-logo-{slug}",
            "source": "gilbarbara",
            "slug": slug,
            "url": GB_FILE_URL.format(file=primary),
            "files": sorted(files),
        })
    return out


def build():
    entries = {}
    ts = thesvg_entries()
    for e in ts:
        entries[e["name"]] = e
    gb = gilbarbara_entries()
    added_gb = 0
    for e in gb:
        if e["name"] not in entries:
            entries[e["name"]] = e
            added_gb += 1
    mirror = sorted(entries.values(), key=lambda e: e["name"])
    manifest = {
        "_comment": (
            "Reference-only mirror of the two public fallback logo libraries, "
            "keyed under this repo's naming convention. NO image bytes are stored "
            "here — every entry's `url` resolves to an upstream jsDelivr file. "
            "Convention: lib-logo-<upstream-slug>. theSVG wins on slug collisions "
            "(multi-variant), gilbarbara fills gaps. Curated files in this repo "
            "always take precedence over a lib- mirror entry for the same brand. "
            "Regenerate with refresh_mirror.py. Variant resolution: theSVG swap "
            "/default.svg -> /<variant>.svg; gilbarbara pick the matching name from `files`."
        ),
        "generated_from": {"thesvg": THESVG_TREE, "gilbarbara": GILBARBARA_INDEX},
        "url_patterns": {"thesvg": TS_FILE_URL, "gilbarbara": GB_FILE_URL},
        "counts": {
            "total": len(mirror),
            "thesvg": len(ts),
            "gilbarbara_net_new": added_gb,
            "gilbarbara_deduped": len(gb) - added_gb,
        },
        "mirror": mirror,
    }
    return manifest


if __name__ == "__main__":
    m = build()
    with open("mirror.manifest.json", "w") as f:
        json.dump(m, f, indent=2)
        f.write("\n")
    print("wrote mirror.manifest.json:", m["counts"])

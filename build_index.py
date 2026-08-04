#!/usr/bin/env python3
"""Write curated.json — the file list the Logo Wall renders.

The wall used to get this list from jsDelivr's package-metadata API
(data.jsdelivr.com/v1/packages/gh/...@main). That endpoint snapshots a branch
and will not re-crawl on demand, so after the Jul 2026 <type>-<category>-<Name>
rename it kept serving the old filenames and every curated thumbnail 404'd.
This index is generated from the working tree instead, committed alongside the
images, and served same-origin from Pages, so it can't drift from the repo.

Run after adding or renaming any logo: python3 build_index.py
The wall-index GitHub Action also runs it on every push to main.
"""
import json
import os

IMG_EXT = (".svg", ".png", ".gif", ".jpg", ".jpeg", ".webp")
# Screenshots are repo assets but not brand marks — keep them out of the wall.
SKIP_PREFIX = ("product-",)

here = os.path.dirname(os.path.abspath(__file__))
names = sorted(
    f for f in os.listdir(here)
    if f.lower().endswith(IMG_EXT) and not f.startswith(SKIP_PREFIX)
)

out = os.path.join(here, "curated.json")
with open(out, "w") as fh:
    json.dump({"files": names}, fh, indent=1)
    fh.write("\n")

print(f"curated.json: {len(names)} files")

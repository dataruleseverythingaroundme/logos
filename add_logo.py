#!/usr/bin/env python3
"""Add one curated logo to the repo the right way: fetch/copy the art, validate
it, name it to convention, dedupe, register it in logos.manifest.json, stamp
freshness.json, and rebuild curated.json.

Used by the /logo slash command and by hand. It shares the same resolvers as
refresh_logos.py so a logo added here is checked identically by the biweekly job.

  <type>-<category>-<Name>.<ext>   type: logo (default) | icon
  categories: data bi cloud comms firm output ai Tellius

Examples:
  python3 add_logo.py --out logo-bi-Cube      --category bi   --url https://cube.dev/.../cube-logo.svg
  python3 add_logo.py --out logo-bi-Omni      --category bi   --search "Omni Analytics"
  python3 add_logo.py --out logo-data-Foo     --category data --commons "Foo logo.svg"
  python3 add_logo.py --out logo-firm-Bar     --category firm --file /path/to/bar.svg --note "from bar.com media kit"
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import refresh_logos as R  # HERE, IMG_EXT, TODAY, resolvers, http_bytes, validate_image

MANIFEST = os.path.join(R.HERE, "logos.manifest.json")
FRESHNESS = os.path.join(R.HERE, "freshness.json")
MIRROR = os.path.join(R.HERE, "mirror.manifest.json")
VALID_CATEGORIES = {"data", "bi", "cloud", "comms", "firm", "output", "ai", "Tellius"}

SNIFF = [(b"<svg", ".svg"), (b"<?xml", ".svg"), (b"\x89PNG\r\n\x1a\n", ".png"),
         (b"GIF8", ".gif"), (b"\xff\xd8\xff", ".jpg"), (b"RIFF", ".webp")]


def sniff_ext(data):
    for sig, ext in SNIFF:
        if data[:64].lstrip().startswith(sig) if ext == ".svg" else data.startswith(sig):
            return ext
    return None


def mirror_slugs():
    try:
        m = json.load(open(MIRROR))
        return {e["name"].lower(): e for e in m.get("mirror", [])}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="filename stem, e.g. logo-bi-Cube (no extension)")
    ap.add_argument("--category", required=True, choices=sorted(VALID_CATEGORIES))
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--commons")
    src.add_argument("--search")
    src.add_argument("--file", help="local path to copy from")
    ap.add_argument("--note", default=None)
    ap.add_argument("--force", action="store_true", help="overwrite if the stem already exists")
    args = ap.parse_args()

    stem = args.out
    if not stem.startswith(("logo-", "icon-")):
        sys.exit(f"error: --out must start with logo- or icon- (got {stem!r})")

    # dedupe: curated file already present?
    existing = R.find_committed(stem)
    if existing and not args.force:
        sys.exit(f"error: {os.path.basename(existing)} already exists. Use --force to replace, "
                 f"or a different --out.")

    # resolve bytes + extension + source string + fingerprint
    fingerprint = None
    if args.file:
        with open(args.file, "rb") as fh:
            data = fh.read()
        ext = os.path.splitext(args.file)[1].lower() or sniff_ext(data)
        source_key, source_val = "local", args.file
    elif args.url:
        fingerprint, url, ext, data = R.resolve_url(args.url)
        ext = ext or sniff_ext(data)
        source_key, source_val = "url", args.url
    elif args.commons:
        fingerprint, url, ext = R.resolve_commons(args.commons)
        data = R.http_bytes(url)
        source_key, source_val = "commons", args.commons
    else:
        fingerprint, url, ext = R.resolve_wikidata(args.search)
        data = R.http_bytes(url)
        source_key, source_val = "search", args.search

    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in R.IMG_EXT:
        sys.exit(f"error: could not determine a valid image extension (got {ext!r})")
    if not R.validate_image(data, ext):
        sys.exit(f"error: fetched bytes did not validate as {ext}")

    filename = stem + ext
    dest = os.path.join(R.HERE, filename)

    # informational: is there a mirror entry that already covers this brand?
    ms = mirror_slugs()
    hint = next((k for k in ms if stem.split("-")[-1].lower() in k), None)
    if hint:
        print(f"note: mirror already indexes {hint!r} — vendoring a curated copy anyway (curated wins).")

    with open(dest, "wb") as fh:
        fh.write(data)
    print(f"wrote {filename} ({len(data):,} bytes, {source_key})")

    # register in logos.manifest.json (append to brands[], drop from gaps if listed)
    man = json.load(open(MANIFEST))
    man["brands"] = [b for b in man["brands"] if b.get("out") != stem]
    if source_key == "local":
        # Hand-sourced bytes: the temp path is meaningless later, so record
        # provenance as a note rather than a bogus local: path. Nothing for the
        # biweekly job to re-check, so it will age (human re-check nudge).
        entry = {"out": stem, "category": args.category,
                 "note": args.note or f"hand-added ({filename}) on {R.TODAY}; no re-checkable source yet"}
    else:
        entry = {"out": stem, "category": args.category, source_key: source_val}
        if args.note:
            entry["note"] = args.note
    man["brands"].append(entry)
    before = len(man.get("gaps_no_source_yet", []))
    man["gaps_no_source_yet"] = [g for g in man.get("gaps_no_source_yet", []) if g.get("out") != stem]
    if len(man.get("gaps_no_source_yet", [])) < before:
        print(f"  (removed {stem} from gaps_no_source_yet — it now has a source)")
    with open(MANIFEST, "w") as fh:
        json.dump(man, fh, indent=2)
        fh.write("\n")

    # stamp freshness.json — an add is a human verification moment, so verified=today
    # either way; url/commons/search also record a fingerprint so the biweekly job can
    # re-verify, while a hand-added file has nothing to re-check and will simply age.
    fresh = json.load(open(FRESHNESS)) if os.path.exists(FRESHNESS) else {"files": {}}
    rec = {"updated": R.TODAY, "verified": R.TODAY, "status": "added"}
    if source_key in ("url", "commons", "search"):
        rec["source"] = f"{source_key}:{source_val}"
        rec["src_hash"] = fingerprint
    else:
        rec["source"] = "file"
    fresh.setdefault("files", {})[filename] = rec
    with open(FRESHNESS, "w") as fh:
        json.dump(fresh, fh, indent=1)
        fh.write("\n")

    # rebuild curated.json
    subprocess.run([sys.executable, os.path.join(R.HERE, "build_index.py")], check=True)

    cdn = f"https://cdn.jsdelivr.net/gh/dataruleseverythingaroundme/logos@main/{filename}"
    print(f"done: {filename}\n  link: {cdn}")


if __name__ == "__main__":
    main()

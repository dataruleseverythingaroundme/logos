#!/usr/bin/env python3
"""Re-check every curated brand mark against its original source and stamp
freshness.

This is the script the manifest and README have always pointed at. For each
entry in `logos.manifest.json` -> `brands[]` it resolves the *current* upstream
artwork and compares it to what's committed here:

  search  -> Wikidata entity (wbsearchentities) -> P154 "logo image" ->
             Wikimedia Commons file (imageinfo sha1 + download url)
  commons -> that Commons filename directly (imageinfo sha1 + url)
  url     -> GET the URL and hash the bytes
  local   -> copied from a local path at build time; no live upstream to verify
  self    -> first-party Tellius mark; it *is* the source, nothing to verify

The result is written to `freshness.json`, a same-origin sidecar the Logo Wall
reads to draw each card's freshness pill. Per file we record:

  verified  last date we confirmed the committed file still matches upstream
  updated   last date the committed bytes actually changed (or were first added)
  source    which manifest source powered it (search:/commons:/url:/local/self)
  status    verified | updated | added | manual | product | unverifiable | needs_review
  src_hash  upstream fingerprint (sha1: from Commons, sha256: for url) for drift detection

Safety (this repo pushes straight to main and marketing hotlinks it):
  * The first run for a file only *records* its upstream fingerprint + marks it
    verified; it never overwrites bytes. Drift is only acted on once we have a
    prior fingerprint to compare against.
  * A file is replaced only when the new bytes validate (decode as their type,
    non-trivial size) AND keep the committed extension, so a paste-into-deck
    hotlink like `...logo-bi-Looker.svg` can't 404 or turn into a broken image.
    Anything else is flagged needs_review and left untouched.
  * Any network/lookup failure marks the file unverifiable and leaves it alone;
    it simply ages in the wall until a human (or /logo) looks.

Run:  python3 refresh_logos.py            # verify + refresh, write freshness.json
      python3 refresh_logos.py --dry-run  # report only, write nothing
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "logos.manifest.json")
FRESHNESS = os.path.join(HERE, "freshness.json")
MIRROR = os.path.join(HERE, "mirror.manifest.json")

IMG_EXT = (".svg", ".png", ".gif", ".jpg", ".jpeg", ".webp")
UA = "dataruleseverythingaroundme-logos-refresh/1.0 (+https://dataruleseverythingaroundme.github.io/logos/)"
TIMEOUT = 25
TODAY = datetime.date.today().isoformat()

WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def log(msg):
    print(msg, flush=True)


# Public APIs (Wikidata/Commons especially) rate-limit bursts. Throttle every
# request and back off on 429/5xx so a 130-file CI run doesn't get 429'd.
_last_call = [0.0]
MIN_GAP = 0.34   # seconds between outbound requests
MAX_TRIES = 3


def _open(url, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    for attempt in range(1, MAX_TRIES + 1):
        wait = MIN_GAP - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            _last_call[0] = time.monotonic()
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT).read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_TRIES:
                retry_after = e.headers.get("Retry-After")
                back = float(retry_after) if (retry_after or "").isdigit() else min(2 ** attempt, 8)
                log(f"     (HTTP {e.code}; backing off {back:.0f}s, try {attempt}/{MAX_TRIES})")
                time.sleep(back)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < MAX_TRIES:
                time.sleep(min(2 ** attempt, 6))
                continue
            raise


def http_json(url):
    return json.loads(_open(url, accept="application/json"))


def http_bytes(url):
    return _open(url)


def git_last_touch(path):
    """Date the committed file's bytes last changed, for bootstrapping `updated`."""
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "log", "-1", "--format=%cs", "--", os.path.basename(path)],
            capture_output=True, text=True, timeout=20,
        )
        d = out.stdout.strip()
        return d or TODAY
    except Exception:
        return TODAY


def find_committed(stem):
    """The single committed image file for a manifest stem (e.g. logo-data-Snowflake)."""
    for ext in IMG_EXT:
        p = os.path.join(HERE, stem + ext)
        if os.path.exists(p):
            return p
    # case-insensitive / any-ext fallback
    for f in os.listdir(HERE):
        base, ext = os.path.splitext(f)
        if base == stem and ext.lower() in IMG_EXT:
            return os.path.join(HERE, f)
    return None


def validate_image(path_or_bytes, ext):
    """True if bytes are a plausible, decodable image of the given extension."""
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    if len(data) < 200:
        return False
    ext = ext.lower()
    if ext == ".svg":
        head = data[:600].lstrip()
        return head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in data[:600]
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        # Pillow missing or can't decode — fall back to magic-byte sniff.
        sigs = {
            ".png": b"\x89PNG\r\n\x1a\n",
            ".gif": b"GIF8",
            ".jpg": b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff",
            ".webp": b"RIFF",
        }
        sig = sigs.get(ext)
        return bool(sig and data.startswith(sig))


# --- upstream resolvers -------------------------------------------------------

def resolve_wikidata(term):
    """search term -> ('sha1:...', download_url, ext) for the entity's P154 logo."""
    q = urllib.parse.urlencode({
        "action": "wbsearchentities", "search": term, "language": "en",
        "format": "json", "type": "item", "limit": 1,
    })
    hits = http_json(f"{WD_API}?{q}").get("search", [])
    if not hits:
        raise LookupError(f"no Wikidata entity for {term!r}")
    qid = hits[0]["id"]
    q = urllib.parse.urlencode({
        "action": "wbgetclaims", "entity": qid, "property": "P154", "format": "json",
    })
    claims = http_json(f"{WD_API}?{q}").get("claims", {}).get("P154", [])
    if not claims:
        raise LookupError(f"{term!r} ({qid}) has no P154 logo image")
    commons_file = claims[0]["mainsnak"]["datavalue"]["value"]
    return resolve_commons(commons_file)


def resolve_commons(filename):
    """Commons filename -> ('sha1:...', download_url, ext)."""
    q = urllib.parse.urlencode({
        "action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
        "iiprop": "sha1|url|mime|size", "format": "json",
    })
    pages = http_json(f"{COMMONS_API}?{q}").get("query", {}).get("pages", {})
    info = next(iter(pages.values()), {})
    ii = (info.get("imageinfo") or [None])[0]
    if not ii:
        raise LookupError(f"Commons file not found: {filename}")
    # Commons now appends ?utm_source=… tracking params to the url; parse the
    # extension off the path only, or fall back to the source filename's ext.
    ext = os.path.splitext(urllib.parse.urlparse(ii["url"]).path)[1] or os.path.splitext(filename)[1]
    return f"sha1:{ii['sha1']}", ii["url"], ext.lower()


def resolve_url(url):
    """direct URL -> ('sha256:...', url, ext, bytes)."""
    data = http_bytes(url)
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return f"sha256:{hashlib.sha256(data).hexdigest()}", url, ext, data


# --- per-brand check ----------------------------------------------------------

def check_brand(b, prev, dry_run):
    """Return a freshness record dict for one manifest brand entry."""
    stem = b["out"]
    committed = find_committed(stem)
    if committed is None:
        return None, f"  !! {stem}: no committed file found; skipping"
    fname = os.path.basename(committed)
    committed_ext = os.path.splitext(fname)[1].lower()
    p = prev.get(fname, {})
    updated = p.get("updated") or git_last_touch(committed)
    rec = {"updated": updated}

    # sources with nothing to verify against
    if b.get("self"):
        rec.update(source="self", status="manual")
        return (fname, rec), f"  ·  {fname}: first-party (self), no upstream"
    if "local" in b:
        rec.update(source="local", status="manual", verified=p.get("verified"))
        return (fname, rec), f"  ·  {fname}: local copy, cannot auto-verify (ages)"

    # externally-sourced: resolve current upstream fingerprint
    try:
        dl_bytes = None
        if "search" in b:
            src = "search:" + b["search"]
            cur_hash, dl_url, up_ext = resolve_wikidata(b["search"])
        elif "commons" in b:
            src = "commons:" + b["commons"]
            cur_hash, dl_url, up_ext = resolve_commons(b["commons"])
        elif "url" in b:
            src = "url:" + b["url"]
            cur_hash, dl_url, up_ext, dl_bytes = resolve_url(b["url"])
        else:
            rec.update(source="unknown", status="manual", verified=p.get("verified"))
            return (fname, rec), f"  ·  {fname}: no source key in manifest (ages)"
    except Exception as e:
        rec.update(source=_src_of(b), status="unverifiable", verified=p.get("verified"),
                   src_hash=p.get("src_hash"), note=str(e)[:200])
        return (fname, rec), f"  ?? {fname}: unverifiable — {str(e)[:120]}"

    rec["source"] = src
    prior = p.get("src_hash")

    # first sighting: record fingerprint, mark verified, never overwrite
    if not prior:
        rec.update(status="verified", verified=TODAY, src_hash=cur_hash)
        return (fname, rec), f"  +  {fname}: fingerprint recorded, verified"

    # unchanged upstream
    if prior == cur_hash:
        rec.update(status="verified", verified=TODAY, src_hash=cur_hash)
        return (fname, rec), f"  =  {fname}: unchanged, verified"

    # upstream changed — refresh only if safe
    up_ext = ".jpg" if up_ext == ".jpeg" else up_ext
    safe_ext = committed_ext if committed_ext != ".jpeg" else ".jpg"
    if up_ext != safe_ext:
        rec.update(status="needs_review", verified=p.get("verified"), src_hash=prior,
                   note=f"upstream now {up_ext}, committed {committed_ext} — ext change, not auto-applied")
        return (fname, rec), f"  !  {fname}: upstream changed to {up_ext} (was {committed_ext}) — flagged needs_review"

    try:
        if dl_bytes is None:
            dl_bytes = http_bytes(dl_url)
    except Exception as e:
        rec.update(status="unverifiable", verified=p.get("verified"), src_hash=prior, note=str(e)[:200])
        return (fname, rec), f"  ?? {fname}: change detected but download failed — {str(e)[:100]}"

    if not validate_image(dl_bytes, committed_ext):
        rec.update(status="needs_review", verified=p.get("verified"), src_hash=prior,
                   note="new upstream bytes failed validation — not applied")
        return (fname, rec), f"  !  {fname}: new upstream failed validation — flagged, kept old"

    if not dry_run:
        with open(committed, "wb") as fh:
            fh.write(dl_bytes)
    rec.update(status="updated", verified=TODAY, updated=TODAY, src_hash=cur_hash)
    verb = "would update" if dry_run else "UPDATED"
    return (fname, rec), f"  *  {fname}: {verb} from upstream (art changed)"


def _src_of(b):
    for k in ("search", "commons", "url", "local", "self"):
        if k in b:
            return k + (":" + str(b[k]) if k not in ("self",) else "")
    return "unknown"


# --- files outside brands[]: product icons + anything uncovered ---------------

def curated_files():
    return sorted(
        f for f in os.listdir(HERE)
        if os.path.splitext(f)[1].lower() in IMG_EXT and not f.startswith("product-")
    )


def mirror_generated_date():
    try:
        m = json.load(open(MIRROR))
        return m.get("generated") or TODAY
    except Exception:
        return TODAY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    manifest = json.load(open(MANIFEST))
    prev = {}
    if os.path.exists(FRESHNESS):
        try:
            prev = json.load(open(FRESHNESS)).get("files", {})
        except Exception:
            prev = {}

    files = {}
    log(f"Refreshing {len(manifest['brands'])} manifest brands against source (today={TODAY})\n")
    for b in manifest["brands"]:
        result, line = check_brand(b, prev, args.dry_run)
        log(line)
        if result:
            files[result[0]] = result[1]

    # Every curated card needs an entry. Fill in product icons + any stragglers.
    covered = set(files)
    for f in curated_files():
        if f in covered:
            continue
        rec = {"updated": prev.get(f, {}).get("updated") or git_last_touch(os.path.join(HERE, f))}
        if f.startswith("icon-"):
            rec.update(source="product", status="product")  # internal product UI icon; nothing to verify
        else:
            rec.update(source=prev.get(f, {}).get("source", "unknown"),
                       status="manual", verified=prev.get(f, {}).get("verified"))
        files[f] = rec

    out = {
        "_comment": (
            "Per-file freshness for the Logo Wall pill. Written by refresh_logos.py "
            "(biweekly Action) and /logo. Dates UTC ISO-8601. status: verified (matched "
            "upstream) | updated (art changed) | added (new via /logo) | manual "
            "(self/local — no live source, ages) | product (internal UI icon) | "
            "unverifiable (source went dead) | needs_review (upstream changed shape). "
            "Pill age = days since max(verified, updated); green<14 amber14-30 red>30; "
            "self/product render neutral."
        ),
        "generated": TODAY,
        "cadence_days": 14,
        "bands": {"green": 14, "amber": 30},
        "mirror_verified": mirror_generated_date(),
        "files": files,
    }
    if args.dry_run:
        log("\n[dry-run] freshness.json NOT written")
    else:
        with open(FRESHNESS, "w") as fh:
            json.dump(out, fh, indent=1)
            fh.write("\n")
        log(f"\nwrote freshness.json: {len(files)} files")

    from collections import Counter
    c = Counter(r["status"] for r in files.values())
    log("status summary: " + json.dumps(dict(c)))
    # non-zero exit hint if anything needs eyes (Action still succeeds; this is informational)
    flagged = c.get("needs_review", 0) + c.get("unverifiable", 0)
    if flagged:
        log(f"NOTE: {flagged} file(s) need a human look (needs_review/unverifiable).")


if __name__ == "__main__":
    main()

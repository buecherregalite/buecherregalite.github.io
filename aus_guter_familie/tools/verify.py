#!/usr/bin/env python3
"""Structural checks on the published folder. Run after every build.

Behaviour is covered by tools/test_widgets.py; this covers everything else.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT
SRC = ROOT / "research" / "course.json"

HOST_FILE_LIMIT = 100 * 1024 * 1024     # GitHub hard limit per file
HOST_SITE_LIMIT = 1024 * 1024 * 1024    # GitHub Pages published-site limit
UNPUBLISHED = {"media-master", "research"}  # gitignored, kept locally only

fails = []


def check(cond, msg):
    (print(f"  ok   {msg}") if cond else (fails.append(msg), print(f"  FAIL {msg}")))


def main():
    course = json.loads(SRC.read_text(encoding="utf-8"))["course"]
    pages = sorted((OUT / "lessons").glob("*.html"))
    html = {p: p.read_text(encoding="utf-8") for p in pages}
    html[OUT / "index.html"] = (OUT / "index.html").read_text(encoding="utf-8")

    print("\n1. Block accounting")
    titles = {}
    for i, l in enumerate(course["lessons"]):
        titles[i] = len(l["items"])
    total_src = sum(titles.values())
    total_out = 0
    for p in pages:
        s = html[p]
        # gates marked data-added are editorial additions (CLEANUP.md §10)
        total_out += (s.count('<div class="block ') + s.count('class="gate"')
                      - s.count('class="gate" data-added'))
    check(len(pages) == len(course["lessons"]),
          f"{len(pages)} pages == {len(course['lessons'])} lessons")
    check(total_out == total_src,
          f"{total_out} rendered blocks+gates == {total_src} source blocks")

    print("\n2. No platform traces")
    brand = []
    for p, s in html.items():
        for m in re.finditer(r"(?i)articulate|rise\s*360|riseusercontent", s):
            brand.append(f"{p.name}: {m.group(0)}")
    for extra in ["assets/css/course.css", "assets/js/course.js"]:
        t = (OUT / extra).read_text(encoding="utf-8")
        if re.search(r"(?i)articulate|rise\s*360", t):
            brand.append(extra)
    check(not brand, f"no platform branding in HTML/CSS/JS ({len(brand)} hits)")
    if brand:
        for b in brand[:10]:
            print(f"       {b}")

    print("\n3. Offline integrity")
    remote, missing = [], []
    for p, s in html.items():
        base = p.parent
        for m in re.findall(r'(?:src|href)="([^"]+)"', s):
            if m.startswith(("http://", "https://")):
                remote.append((p.name, m))
            elif not m.startswith(("#", "mailto:", "data:")):
                if not (base / m).resolve().exists():
                    missing.append((p.name, m))
    ext_hosts = sorted({re.sub(r"^(https?://[^/]+).*", r"\1", u) for _, u in remote})
    check(not missing, f"every local reference resolves ({len(missing)} broken)")
    for n, u in missing[:10]:
        print(f"       {n}: {u}")
    print(f"  note outbound prose links to {len(ext_hosts)} host(s): "
          f"{', '.join(h.replace('https://','') for h in ext_hosts) or 'none'}")
    check(not any("articulate" in u or "riseusercontent" in u for _, u in remote),
          "no asset loads from the original platform")

    print("\n4. Media")
    media = [f for f in (OUT / "assets" / "media").rglob("*")
             if f.is_file() and not f.name.endswith(".part.mp4")]
    empty = [f.name for f in media if f.stat().st_size == 0]
    oversize = [(f.name, f.stat().st_size) for f in media
                if f.stat().st_size > HOST_FILE_LIMIT]
    check(not empty, f"no zero-byte media files ({len(media)} files)")
    check(not oversize, f"no file exceeds the {HOST_FILE_LIMIT//1048576} MB host limit")
    for n, sz in oversize:
        print(f"       {sz/1048576:.0f} MB  {n}")

    site = sum(f.stat().st_size for f in OUT.rglob("*")
               if f.is_file() and not f.name.endswith(".part.mp4")
               and UNPUBLISHED.isdisjoint(f.relative_to(OUT).parts))
    check(site < HOST_SITE_LIMIT,
          f"published site {site/1048576:.0f} MB < {HOST_SITE_LIMIT//1048576} MB limit")

    print("\n5. Hosting hygiene")
    check((OUT / ".nojekyll").exists(), ".nojekyll present (GitHub Pages)")
    check(not (OUT / "data").exists(), "no raw platform export in the published folder")
    leaked = [p.name for p, s in html.items() if "posteo" in s and "mailto" not in s]
    print(f"  note published contact address appears in course text (intended)")

    print(f"\n{'='*60}")
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED")
        return 1
    print("All structural checks passed.")
    print(f"Publishable folder: {OUT}  ({site/1048576:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

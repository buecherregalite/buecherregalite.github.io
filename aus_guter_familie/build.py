#!/usr/bin/env python3
"""
Static archive builder for the course "Reuter: Aus guter Familie (1895)".

Reads research/course.json (the frozen source of truth), mirrors the media it
references, and emits a fully self-contained static site directly into this
folder (index.html, lessons/, assets/) that works from file:// with no
network access and no build tooling.

Usage:
    python3 build.py                # build the lessons in LESSONS
    python3 build.py --all          # build every lesson
    python3 build.py --no-media     # skip the media mirror (HTML only)

stdlib only, by design: nothing here should rot.
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "research" / "course.json"
STATIC = ROOT / "static"
OUT = ROOT

CDN = "https://articulateusercontent.com/"

# Lessons to build, by index into course.lessons. Array order == sidebar order;
# `position` in the JSON is corrupt and must not be used for sorting.
LESSONS = [1, 2]

# ---------------------------------------------------------------------------
# Editorial cleanup
# ---------------------------------------------------------------------------
# The live course contains untranslated Rise authoring placeholders. The course
# author has asked for these to be cleaned up rather than reproduced verbatim.
# Every substitution is recorded here and mirrored in CLEANUP.md so the edit is
# auditable and reversible.

PLACEHOLDER_RESPONSES = {
    "End this scenario.": "Weiter",
    "I want to do the scenario again.": "Szenario von vorne beginnen",
    "Learners who choose this response will continue on.": "Weiter",
}

# Responses whose text AND feedback are pure boilerplate carry no meaning and
# are dropped entirely.
DROP_RESPONSES = {
    "Learners who choose this incorrect response will be able to try again.",
}

DROP_FEEDBACK = {
    "Add feedback here to let learners know they got it right.",
    "Add helpful feedback here and let learners try again.",
}

cleanup_log = []


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("&nbsp;", " ").strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(s):
    return html.escape(s or "", quote=True)


def rich(s):
    """Content fields arrive as HTML strings with entities already encoded.
    Emit them raw. Plain-text fields (quiz answer labels, etc.) get escaped."""
    s = s or ""
    return s if s.lstrip().startswith("<") else esc(s)


def slugify(s, maxlen=60):
    s = strip_tags(s)
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
          .replace("Ä", "ae").replace("Ö", "oe").replace("Ü", "ue")
          .replace("ß", "ss"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].strip("-") or "lektion"


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

KIND_DIR = {"image": "img", "video": "video", "audio": "audio",
            "attachment": "files"}

media_map = {}     # original key or absolute url -> relative path from lesson page
media_jobs = {}    # url -> {kind, master, web}

# Originals are downloaded once into MASTER and kept there as the personal
# archive. The published site is derived from them: images, audio and PDFs are
# copied unchanged, video is re-encoded to fit a web budget.
MASTER = ROOT / "media-master"

VIDEO_CAP_MB = 90          # stay clear of the 100 MB per-file host limit
# Tried in order until the result fits. Audio bitrate never drops: for this
# course the spoken word is the payload and the picture is secondary.
VIDEO_LADDER = [(720, 23), (720, 27), (540, 28), (480, 30), (360, 32)]


def local_for(key_or_url, kind):
    """Register a media asset and return its path relative to lessons/."""
    if key_or_url in media_map:
        return media_map[key_or_url]

    if key_or_url.startswith("http"):
        url = key_or_url
        base = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    else:
        url = CDN + key_or_url
        base = key_or_url.rsplit("/", 1)[-1]

    # Keys are already URL-encoded (some contain a literal %2520). Decode only
    # to derive a readable local filename; the fetch always uses the raw key.
    nice = urllib.parse.unquote(urllib.parse.unquote(base))
    nice = re.sub(r"^transcoded-", "", nice)
    nice = re.sub(r"^[A-Za-z0-9_-]{16}-", "", nice)   # strip upload hash prefix
    stem, ext = os.path.splitext(nice)
    stem = slugify(stem, 48) or "asset"
    ext = (ext or "").lower()[:6]
    if not re.fullmatch(r"\.[a-z0-9]+", ext):
        ext = {"image": ".jpg", "video": ".mp4",
               "audio": ".mp3", "attachment": ".bin"}[kind]

    digest = hashlib.sha1(key_or_url.encode()).hexdigest()[:8]
    name = f"{digest}-{stem}{ext}"
    sub = KIND_DIR[kind]

    media_jobs[url] = {
        "kind": kind,
        "master": MASTER / sub / name,
        "web": OUT / "assets" / "media" / sub / name,
    }
    rel = f"../assets/media/{sub}/{name}"
    media_map[key_or_url] = rel
    return rel


POSTER_TF = "f:jpg,w:1920,q:90"


def poster_src(url):
    """Video posters come from the images.articulate.com resizing proxy. The
    transform Rise stores (`f:png,...,q:65`) returns a 16-colour PNG - fine for
    a flat title card, poor for anything else. Ask for a full-colour JPEG
    instead; the proxy dies with the rest of the site, so this is the only
    chance to get a good frame."""
    m = re.match(r"^(https://images\.articulate\.com/)([^/]*:[^/]*)/(.+)$", url)
    if m:
        url = f"{m.group(1)}{POSTER_TF}/{m.group(3)}"
    return local_for(url, "image")


MAGIC = {
    b"\xff\xd8\xff": {".jpg", ".jpeg"},
    b"\x89PNG": {".png"},
    b"GIF8": {".gif"},
    b"%PDF": {".pdf"},
    b"ID3": {".mp3"},
}


def sniff_mismatch(path):
    """Return a warning string if a file's bytes disagree with its extension."""
    head = open(path, "rb").read(12)
    ext = path.suffix.lower()
    for magic, exts in MAGIC.items():
        if head.startswith(magic):
            return None if ext in exts else f"{path.name}: content is {sorted(exts)[0]}"
    if head[4:8] == b"ftyp":                       # ISO-BMFF: mp4/m4a
        return None if ext in {".mp4", ".m4a", ".m4v", ".mov"} else f"{path.name}: content is .mp4"
    return None


def img_src(image):
    """Resolve an image media object to a local path. Always archives the full
    original, never the smaller `crushedKey` re-encode."""
    if not image:
        return None
    key = image.get("key")
    if not key:
        return None
    return local_for(key, "image")


def download_all(jobs):
    """Fetch every original into MASTER. This is the personal archive and the
    only perishable step - the source disappears, the masters do not."""
    todo = [(u, j) for u, j in jobs.items()
            if not (j["master"].exists() and j["master"].stat().st_size > 0)]
    if not todo:
        print(f"  originals: all {len(jobs)} already in {MASTER.name}/")
    else:
        print(f"  originals: fetching {len(todo)} of {len(jobs)} into {MASTER.name}/")
        failures = []

        def fetch(item):
            # curl rather than urllib: the system Python on macOS ships without
            # a usable CA bundle, and curl resumes partial transfers.
            url, job = item
            path = job["master"]
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            try:
                r = subprocess.run(
                    ["curl", "-sSL", "--fail", "--retry", "3", "--retry-delay", "2",
                     "--connect-timeout", "30", "--continue-at", "-",
                     "-A", "Mozilla/5.0", "-o", str(tmp), url],
                    capture_output=True, text=True, timeout=3600)
                if r.returncode != 0:
                    raise IOError((r.stderr or "").strip() or f"curl exit {r.returncode}")
                head = open(tmp, "rb").read(64).lstrip()
                # A failed fetch can arrive as 200 with an HTML or JSON error body.
                if tmp.stat().st_size == 0 or head.startswith(b"<!DOCTYPE") or head.startswith(b'{"error'):
                    raise IOError("bad payload")
                tmp.rename(path)
                return (url, path.stat().st_size, None)
            except Exception as e:
                tmp.unlink(missing_ok=True)
                return (url, 0, str(e))

        with ThreadPoolExecutor(max_workers=8) as ex:
            for url, size, err in ex.map(fetch, todo):
                if err:
                    failures.append((url, err))
                    print(f"    FAIL {err}  {url}", file=sys.stderr)
                else:
                    print(f"    got {size/1048576:8.1f} MB  {url.rsplit('/',1)[-1][:56]}", flush=True)

        if failures:
            raise SystemExit(f"\n{len(failures)} download(s) failed - aborting.")

    bad = [w for w in (sniff_mismatch(j["master"]) for j in jobs.values()
                       if j["master"].exists()) if w]
    if bad:
        print("  WARNING: extension/content mismatch:")
        for w in bad:
            print(f"    {w}")


def probe_height(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=height", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip().splitlines()[0])
    except Exception:
        return 0


def encode_video(src, dst):
    """Re-encode down the quality ladder until the file fits VIDEO_CAP_MB.
    Audio is held at 128k AAC throughout - for this course the spoken word is
    the content and the picture is supporting material."""
    src_h = probe_height(src) or 1080
    cap = VIDEO_CAP_MB * 1048576
    tmp = dst.with_suffix(".part.mp4")
    last = None
    for height, crf in VIDEO_LADDER:
        h = min(height, src_h)
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", f"scale=-2:{h}", "-c:v", "libx264", "-crf", str(crf),
             "-preset", "medium", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)],
            capture_output=True, text=True, timeout=7200)
        if r.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise IOError((r.stderr or "").strip()[:300] or "ffmpeg failed")
        size = tmp.stat().st_size
        last = (h, crf, size)
        if size <= cap:
            break
        # too big - try the next rung rather than shipping an unhostable file
    tmp.rename(dst)
    return last


def derive_web(jobs):
    """Build the publishable media set from the masters."""
    vids = [(u, j) for u, j in jobs.items() if j["kind"] == "video"]
    others = [(u, j) for u, j in jobs.items() if j["kind"] != "video"]

    n = 0
    for _, j in others:
        j["web"].parent.mkdir(parents=True, exist_ok=True)
        if not (j["web"].exists() and j["web"].stat().st_size == j["master"].stat().st_size):
            shutil.copy2(j["master"], j["web"])
            n += 1
    print(f"  web media: copied {n} image/audio/pdf file(s) unchanged")

    todo = [(u, j) for u, j in vids if not (j["web"].exists() and j["web"].stat().st_size > 0)]
    if not todo:
        print(f"  web video: all {len(vids)} already encoded")
        return
    print(f"  web video: encoding {len(todo)} of {len(vids)} "
          f"(720p target, cap {VIDEO_CAP_MB} MB, audio 128k)")
    for i, (_, j) in enumerate(todo, 1):
        j["web"].parent.mkdir(parents=True, exist_ok=True)
        before = j["master"].stat().st_size / 1048576
        h, crf, size = encode_video(j["master"], j["web"])
        print(f"    [{i}/{len(todo)}] {before:7.0f} MB -> {size/1048576:6.1f} MB  "
              f"{h}p crf{crf}  {j['web'].name[:44]}", flush=True)


# ---------------------------------------------------------------------------
# Block chrome
# ---------------------------------------------------------------------------

PAD = {0: 0, 1: 10, 2: 18, 3: 28, 4: 44, 5: 62}


def block_attrs(b):
    s = b.get("settings") or {}
    cls = ["block", f"b-{b.get('family','')}".replace(" ", "-"),
           f"v-{(b.get('variant') or '').replace(' ', '-')}"]
    bt = (s.get("backgroundType") or "LIGHT").upper()
    cls.append(f"bg-{bt.lower()}")
    style = (f"padding-top:{PAD.get(s.get('paddingTop', 3), 48)}px;"
             f"padding-bottom:{PAD.get(s.get('paddingBottom', 3), 48)}px")
    return f'class="{" ".join(cls)}" style="{style}"'


def wrap(b, inner):
    return f'<div {block_attrs(b)}><div class="inner">{inner}</div></div>'


# ---------------------------------------------------------------------------
# Renderers, one per (family, variant)
# ---------------------------------------------------------------------------

def r_text(b):
    out = []
    for it in b["items"]:
        if it.get("heading"):
            out.append(f'<div class="h">{rich(it["heading"])}</div>')
        if it.get("paragraph"):
            out.append(f'<div class="p">{rich(it["paragraph"])}</div>')
    return wrap(b, "".join(out))


def r_impact(b):
    body = "".join(f'<div class="p">{rich(it.get("paragraph"))}</div>'
                   for it in b["items"])
    return wrap(b, f'<aside class="note">{body}</aside>')


def r_divider(b):
    return wrap(b, '<hr class="rule">')


def r_quote(b):
    v = b.get("variant")
    out = []
    for it in b["items"]:
        av = img_src(((it.get("avatar") or {}).get("media") or {}).get("image"))
        avatar = f'<img class="avatar" src="{av}" alt="">' if av else ""
        name = f'<div class="qname">{rich(it.get("name"))}</div>' if it.get("name") else ""
        style = ""
        if v == "background":
            bg = img_src(((it.get("background") or {}).get("media") or {}).get("image"))
            if bg:
                style = f' style="background-image:url({bg})"'
        out.append(f'<figure class="quote"{style}>{avatar}'
                   f'<blockquote>{rich(it.get("paragraph"))}</blockquote>'
                   f'<figcaption>{name}</figcaption></figure>')

    if v == "carousel" and len(out) > 1:
        slides = "".join(f'<div class="q-slide"{"" if i == 0 else " hidden"}>{q}</div>'
                         for i, q in enumerate(out))
        dots = "".join(f'<button class="q-dot" data-i="{i}" '
                       f'aria-label="{i+1}"></button>' for i in range(len(out)))
        return wrap(b, f'<div class="q-carousel"><div class="q-slides">{slides}</div>'
                       f'<div class="q-nav"><button class="btn ghost prev" '
                       f'aria-label="Zurück">‹</button>'
                       f'<div class="q-dots">{dots}</div>'
                       f'<button class="btn ghost next" aria-label="Weiter">›</button>'
                       f'</div></div>')
    return wrap(b, "".join(out))


def r_list(b):
    variant = b.get("variant")
    if variant == "checkboxes":
        rows = []
        for it in b["items"]:
            cid = f'cb-{b["id"]}-{it["id"]}'
            rows.append(
                f'<li><input type="checkbox" id="{cid}" data-persist="{cid}">'
                f'<label for="{cid}">{rich(it.get("paragraph"))}</label></li>')
        return wrap(b, f'<ul class="checklist">{"".join(rows)}</ul>')
    rows = "".join(f"<li>{rich(it.get('paragraph'))}</li>" for it in b["items"])
    return wrap(b, f'<ul class="bullets">{rows}</ul>')


def _figure(it, cls, zoom):
    src = img_src((it.get("media") or {}).get("image"))
    if not src:
        return ""
    dims = ((it.get("media") or {}).get("image") or {}).get("dimensions") or {}
    wh = ""
    if dims.get("originalWidth"):
        wh = f' width="{dims["originalWidth"]}" height="{dims.get("originalHeight","")}"'
    z = ' data-zoom="1"' if zoom else ""
    cap = (f'<figcaption>{rich(it.get("caption"))}</figcaption>'
           if strip_tags(it.get("caption")) else "")
    return (f'<figure class="{cls}">'
            f'<img src="{src}" alt="" loading="lazy"{wh}{z}>{cap}</figure>')


def r_image(b):
    v = b.get("variant")
    zoom = bool((b.get("settings") or {}).get("zoomOnClick"))
    if v == "text aside":
        it = b["items"][0]
        fig = _figure(it, "aside-fig", zoom)
        txt = f'<div class="p">{rich(it.get("paragraph"))}</div>'
        return wrap(b, f'<div class="text-aside">{fig}{txt}</div>')
    if v == "text overlay":
        it = b["items"][0]
        src = img_src((it.get("media") or {}).get("image"))
        return wrap(b, f'<figure class="overlay"><img src="{src}" alt="" loading="lazy">'
                       f'<figcaption>{rich(it.get("caption"))}</figcaption></figure>')
    return wrap(b, "".join(_figure(it, "hero-fig", zoom) for it in b["items"]))


def r_gallery(b):
    n = 4 if b.get("variant") == "four column" else 3
    cells = "".join(_figure(it, "cell", True) for it in b["items"])
    return wrap(b, f'<div class="gallery cols-{n}">{cells}</div>')


def r_multimedia(b):
    v = b.get("variant")
    out = []
    for it in b["items"]:
        m = it.get("media") or {}
        cap = (f'<figcaption>{rich(it.get("caption"))}</figcaption>'
               if strip_tags(it.get("caption")) else "")
        if v == "video":
            vid = m.get("video") or {}
            src = local_for(vid["key"], "video")
            poster = poster_src(vid["poster"]) if vid.get("poster") else None
            pa = f' poster="{poster}"' if poster else ""
            out.append(f'<figure class="media"><video controls preload="metadata"'
                       f'{pa} src="{src}"></video>{cap}</figure>')
        elif v == "audio":
            aud = m.get("audio") or {}
            src = local_for(aud["key"], "audio")
            out.append(f'<figure class="media"><audio controls preload="metadata" '
                       f'src="{src}"></audio>{cap}</figure>')
        elif v == "attachment":
            at = m.get("attachment") or {}
            src = local_for(at["key"], "attachment")
            name = urllib.parse.unquote(at.get("originalUrl") or at.get("filename") or "Download")
            size = at.get("size") or 0
            kb = f"{size/1048576:.1f} MB" if size > 1048576 else f"{max(size,0)//1024} KB"
            out.append(f'<a class="attach" href="{src}" download>'
                       f'<span class="attach-ico" aria-hidden="true">↓</span>'
                       f'<span class="attach-name">{esc(name)}</span>'
                       f'<span class="attach-meta">{kb}</span></a>{cap}')
    return wrap(b, "".join(out))


def r_knowledgecheck(b):
    it = b["items"][0]
    v = b.get("variant")
    qid = b["id"]
    title = f'<div class="kc-q">{rich(it.get("title"))}</div>'
    fb = strip_tags(it.get("feedback"))
    fb_html = (f'<div class="kc-feedback" hidden>{rich(it.get("feedback"))}</div>'
               if fb else "")

    if v == "matching":
        # `correct` is NOT meaningful here. Across every matching block in the
        # course the rows authored first are true and every row added later is
        # false - the flag is inherited from the multiple-choice answer schema
        # and ignored for MATCHING. Lesson 7 would otherwise have 7 of its 10
        # pairs unanswerable. Each row's title <-> matchTitle IS the answer.
        answers = it["answers"]
        rows = "".join(
            f'<div class="match-row" data-answer="{esc(a["matchTitle"])}">'
            f'<span class="match-left">{rich(a["title"])}</span>'
            f'<span class="match-slot" data-slot></span></div>'
            for a in answers)
        # Chips are shuffled deterministically (by sorted label) so the pool
        # order never gives the pairing away.
        chips = "".join(
            f'<button type="button" class="chip" draggable="true" '
            f'data-value="{esc(v)}">{esc(v.strip())}</button>'
            for v in sorted({a["matchTitle"] for a in answers}))
        body = (f'<div class="match">'
                f'<p class="hint">Ziehen Sie die Antworten auf die passende Aussage — '
                f'oder antippen und dann die Zeile anklicken.</p>'
                f'<div class="match-pool" data-slot>{chips}</div>'
                f'<div class="match-rows">{rows}</div></div>')

    elif v == "fillin":
        accepted = [strip_tags(a["title"]) for a in it["answers"]]
        body = (f'<div class="fillin"><input type="text" '
                f'data-accept=\'{esc(json.dumps(accepted, ensure_ascii=False))}\' '
                f'autocomplete="off" spellcheck="false"></div>')

    else:  # multiple choice / multiple response
        # Trust the answer data, not the variant label. Two blocks typed
        # "multiple choice" have five correct answers each (lesson 5 "Gabriele
        # Reuter hat...", lesson 16 "Fur welche Arten von Text..."); rendering
        # those as radio buttons makes them unanswerable. Radios only when
        # exactly one answer is correct.
        n_correct = sum(1 for a in it["answers"] if a.get("correct"))
        typ = "radio" if n_correct == 1 else "checkbox"
        rows = []
        for i, a in enumerate(it["answers"]):
            aid = f"kc-{qid}-{i}"
            rows.append(
                f'<li><input type="{typ}" name="kc-{qid}" id="{aid}" '
                f'data-correct="{"1" if a.get("correct") else "0"}">'
                f'<label for="{aid}">{rich(a["title"])}</label></li>')
        body = f'<ul class="kc-options">{"".join(rows)}</ul>'

    return wrap(b, f'<div class="kc" data-kc="{v}" data-id="{qid}">{title}{body}'
                   f'<div class="kc-actions">'
                   f'<button class="btn kc-submit">Senden</button>'
                   f'<button class="btn ghost kc-retry" hidden>Nochmal versuchen</button>'
                   f'</div><div class="kc-result" hidden></div>{fb_html}</div>')


def r_flashcard(b):
    v = b.get("variant")
    cards = []
    for it in b["items"]:
        f_img = img_src(((it.get("front") or {}).get("media") or {}).get("image"))
        bk_img = img_src(((it.get("back") or {}).get("media") or {}).get("image"))
        fi = f'<img src="{f_img}" alt="" loading="lazy">' if f_img else ""
        bi = f'<img src="{bk_img}" alt="" loading="lazy">' if bk_img else ""
        cards.append(
            f'<button class="card" aria-pressed="false">'
            f'<span class="card-inner">'
            f'<span class="face front">{fi}<span class="face-txt">'
            f'{rich((it.get("front") or {}).get("description"))}</span></span>'
            f'<span class="face back">{bi}<span class="face-txt">'
            f'{rich((it.get("back") or {}).get("description"))}</span></span>'
            f'</span></button>')
    cls = "flash-stack" if v == "stack" else "flash-grid"
    nav = ('<div class="stack-nav"><button class="btn ghost prev">‹</button>'
           '<span class="stack-pos"></span>'
           '<button class="btn ghost next">›</button></div>') if v == "stack" else ""
    hint = '<p class="hint">Zum Umdrehen anklicken.</p>'
    return wrap(b, f'{hint}<div class="{cls}">{"".join(cards)}</div>{nav}')


def r_interactive(b):
    v = b.get("variant")

    if v == "scenario":
        return r_scenario(b)

    if v == "sorting":
        piles = b.get("piles") or []
        cards = "".join(
            f'<button class="sort-card" data-pile="{it["pileId"]}" '
            f'data-id="{it["id"]}">{esc(it["title"])}</button>'
            for it in b["items"])
        zones = "".join(
            f'<div class="pile" data-pile="{p["id"]}">'
            f'<h4>{esc(p["title"])}</h4><div class="pile-drop"></div></div>'
            for p in piles)
        return wrap(b, f'<div class="sorting"><p class="hint">Karte auswählen, '
                       f'dann Kategorie anklicken.</p>'
                       f'<div class="sort-pool">{cards}</div>'
                       f'<div class="piles">{zones}</div>'
                       f'<div class="kc-actions"><button class="btn sort-check">Prüfen</button>'
                       f'<button class="btn ghost sort-reset">Zurücksetzen</button></div>'
                       f'<div class="kc-result" hidden></div></div>')

    if v == "process":
        steps = [it for it in b["items"] if not it.get("isHidden")]
        panes = "".join(
            f'<div class="step" {"" if i == 0 else "hidden"}>'
            f'<div class="step-n">{i+1} / {len(steps)}</div>'
            f'<h4>{esc(it.get("title"))}</h4>'
            f'<div class="p">{rich(it.get("description"))}</div></div>'
            for i, it in enumerate(steps))
        return wrap(b, f'<div class="process">{panes}'
                       f'<div class="stack-nav"><button class="btn ghost prev">‹ Zurück</button>'
                       f'<button class="btn next">Weiter ›</button></div></div>')

    if v == "labeledgraphic":
        img = img_src((b.get("media") or {}).get("image")) or ""
        marks, pops = [], []
        for i, it in enumerate(b["items"]):
            marks.append(f'<button class="marker" data-i="{i}" '
                         f'style="left:{it["x"]}%;top:{it["y"]}%" '
                         f'aria-label="{esc(it.get("title"))}">+</button>')
            pops.append(f'<div class="pop" data-i="{i}" hidden>'
                        f'<h4>{esc(it.get("title"))}</h4>'
                        f'<div class="p">{rich(it.get("description"))}</div>'
                        f'<button class="pop-close" aria-label="Schliessen">×</button></div>')
        return wrap(b, f'<div class="lg"><div class="lg-wrap">'
                       f'<img src="{img}" alt="" loading="lazy">'
                       f'{"".join(marks)}</div>{"".join(pops)}</div>')

    if v == "timeline":
        rows = "".join(
            f'<li><div class="tl-date">{esc(it.get("date"))}</div>'
            f'<div class="tl-body"><h4>{esc(it.get("title"))}</h4>'
            f'<div class="p">{rich(it.get("description"))}</div></div></li>'
            for it in b["items"])
        return wrap(b, f'<ol class="timeline">{rows}</ol>')

    if v == "tabs":
        tabs, panes = [], []
        for i, it in enumerate(b["items"]):
            sel = "true" if i == 0 else "false"
            tabs.append(f'<button role="tab" aria-selected="{sel}" data-i="{i}">'
                        f'{esc(it.get("title"))}</button>')
            img = img_src((it.get("media") or {}).get("image"))
            pic = f'<img src="{img}" alt="" loading="lazy">' if img else ""
            panes.append(f'<div role="tabpanel" data-i="{i}" {"" if i == 0 else "hidden"}>'
                         f'{pic}<div class="p">{rich(it.get("description"))}</div></div>')
        return wrap(b, f'<div class="tabs"><div role="tablist">{"".join(tabs)}</div>'
                       f'<div class="panes">{"".join(panes)}</div></div>')

    raise KeyError(f"interactive/{v}")


def r_scenario(b):
    """Branching scenario. Emits every slide as a hidden pane plus an inline
    JSON graph; course.js walks it. Character art is intentionally omitted -
    it was never part of the course data (see CLEANUP.md)."""
    scenes = []
    for scene in b["items"]:
        slides = []
        for s in scene["slides"]:
            responses = []
            for r in s.get("responses") or []:
                label = strip_tags(r.get("description"))
                if label in DROP_RESPONSES:
                    cleanup_log.append(("dropped response", label))
                    continue
                if label in PLACEHOLDER_RESPONSES:
                    new = PLACEHOLDER_RESPONSES[label]
                    cleanup_log.append(("relabelled response", f"{label} -> {new}"))
                    desc = new
                else:
                    desc = r.get("description")
                feedback = r.get("feedback")
                if strip_tags(feedback) in DROP_FEEDBACK:
                    cleanup_log.append(("dropped feedback", strip_tags(feedback)))
                    feedback = None
                responses.append({
                    "html": rich(desc),
                    "action": r.get("action") or "continue",
                    "goTo": r.get("goTo") or "next",
                    "target": ((r.get("nextSlide") or {}).get("slide")),
                    "feedback": rich(feedback) if feedback else None,
                })
            slides.append({
                "id": s["id"],
                "title": s.get("title") or "",
                "html": rich(s.get("description")),
                "goTo": s.get("goTo") or "next",
                "target": ((s.get("nextSlide") or {}).get("slide")),
                "responses": responses,
            })
        scenes.append({"id": scene["id"], "title": scene.get("title") or "",
                       "slides": slides})

    graph = json.dumps({"scenes": scenes}, ensure_ascii=False)
    title = esc(strip_tags(b["items"][0].get("title")))
    return wrap(b, f'<div class="scenario" data-id="{b["id"]}">'
                   f'<div class="scenario-head">{title}</div>'
                   f'<div class="scenario-stage"></div>'
                   f'<script type="application/json" class="scenario-data">{graph}</script>'
                   f'</div>')


RENDERERS = {
    "text": r_text,
    "impact": r_impact,
    "divider": r_divider,
    "quote": r_quote,
    "list": r_list,
    "image": r_image,
    "gallery": r_gallery,
    "multimedia": r_multimedia,
    "knowledgeCheck": r_knowledgecheck,
    "flashcard": r_flashcard,
    "interactive": r_interactive,
    "interactive-fullscreen": r_interactive,
}


def render_block(b):
    fam = b.get("family")
    fn = RENDERERS.get(fam)
    if fn is None:
        raise KeyError(f"no renderer for family={fam!r} variant={b.get('variant')!r}")
    return fn(b)


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

def reveal_groups(items):
    """Split a lesson's blocks on `continue` gates.
    Returns [(blocks, gate_or_None), ...]."""
    groups, cur = [], []
    for b in items:
        if b.get("family") == "continue":
            groups.append((cur, b))
            cur = []
        else:
            cur.append(b)
    if cur or not groups:
        groups.append((cur, None))
    return groups


def page_shell(title, body, css_depth, extra_head="", body_class=""):
    up = "../" if css_depth else ""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{up}assets/css/course.css">
{extra_head}
</head>
<body class="{body_class}">
{body}
<script src="{up}assets/js/course.js"></script>
</body>
</html>
"""


def sidebar(course, built, current=None):
    rows = []
    for i, l in enumerate(course["lessons"]):
        t = strip_tags(l["title"])
        n = i + 1
        if i in built:
            href = f"{n:02d}-{slugify(t)}.html"
            cls = "on" if i == current else ""
            rows.append(f'<li class="{cls}"><a href="{href}">{esc(t)}</a></li>')
        else:
            rows.append(f'<li class="todo"><span>{esc(t)}</span></li>')
    return (f'<nav class="sidebar"><a class="brand" href="{"../" if current is not None else ""}index.html">'
            f'{esc(strip_tags(course["title"]))}</a>'
            f'<ol class="lessons">{"".join(rows)}</ol></nav>')


def build_lesson(course, idx, built):
    l = course["lessons"][idx]
    title = strip_tags(l["title"])
    groups = reveal_groups(l["items"])

    order = sorted(built)
    pos = order.index(idx)

    def lesson_href(i):
        return f'{i+1:02d}-{slugify(strip_tags(course["lessons"][i]["title"]))}.html'

    next_href = lesson_href(order[pos + 1]) if pos < len(order) - 1 else None

    parts = []
    n_blocks = 0
    for gi, (blocks, gate) in enumerate(groups):
        hidden = "" if gi == 0 else " hidden"
        rendered = "".join(render_block(b) for b in blocks)
        n_blocks += len(blocks)

        gate_html = ""
        if gate is not None:
            n_blocks += 1
            label = esc(strip_tags((gate["items"][0] or {}).get("title")) or "Weiter")
            if gi + 1 < len(groups):
                gate_html = (f'<div class="gate" data-gate="{gi}">'
                             f'<button class="btn gate-btn">{label}</button></div>')
            else:
                # A trailing `continue` with nothing after it is the author's
                # end-of-lesson button; in Rise it advances to the next lesson.
                # At the end of the course there is nowhere to go but back to
                # the contents - never drop the block silently.
                if next_href:
                    gate_html = (f'<div class="gate"><a class="btn" '
                                 f'href="{next_href}">{label}</a></div>')
                else:
                    gate_html = ('<div class="gate"><a class="btn" '
                                 'href="../index.html">Zur Übersicht</a></div>')

        # The gate lives inside its group so that hiding the group hides its
        # button too - otherwise every gate in the lesson shows at once.
        parts.append(f'<section class="group" data-group="{gi}"{hidden}>'
                     f'{rendered}{gate_html}</section>')

    assert n_blocks == len(l["items"]), \
        f"lesson {idx}: rendered {n_blocks} of {len(l['items'])} blocks"

    prev_next = []
    if pos > 0:
        prev_next.append(f'<a class="btn ghost" href="{lesson_href(order[pos-1])}">‹ Zurück</a>')
    if next_href:
        prev_next.append(f'<a class="btn" href="{next_href}">Weiter ›</a>')

    body = f"""
{sidebar(course, built, idx)}
<main class="lesson">
  <header class="lesson-head">
    <div class="eyebrow">{esc(strip_tags(course["title"]))}</div>
    <h1>{esc(title)}</h1>
    <button class="btn ghost expand-all">Alles aufklappen</button>
  </header>
  <div class="blocks">{''.join(parts)}</div>
  <footer class="lesson-foot">{''.join(prev_next)}</footer>
</main>
<div class="lightbox" hidden><img alt=""><button class="lb-close" aria-label="Schliessen">×</button></div>
"""
    fname = f"{idx+1:02d}-{slugify(title)}.html"
    (OUT / "lessons" / fname).write_text(
        page_shell(f"{title} — {strip_tags(course['title'])}", body, 1),
        encoding="utf-8")
    return fname, len(l["items"])


def build_index(course, built):
    cover = img_src(((course.get("coverImage") or {}).get("media") or {}).get("image"))
    cover_rel = cover.replace("../", "") if cover else None
    hero_style = f' style="background-image:url({cover_rel})"' if cover_rel else ""

    cards = []
    for i, l in enumerate(course["lessons"]):
        t = strip_tags(l["title"])
        n = i + 1
        if i in built:
            href = f"lessons/{n:02d}-{slugify(t)}.html"
            cards.append(f'<a class="card-l" href="{href}">'
                         f'<span class="ct">{esc(t)}</span>'
                         f'<span class="go" aria-hidden="true">\u203a</span></a>')
        else:
            cards.append(f'<span class="card-l todo">'
                         f'<span class="ct">{esc(t)}</span>'
                         f'<span class="soon">in Arbeit</span></span>')

    body = f"""
<header class="cover"{hero_style}>
  <div class="cover-in">
    <h1>{esc(strip_tags(course['title']))}</h1>
    <div class="cover-desc">{rich(course.get('description'))}</div>
  </div>
</header>
<main class="home">
  <h2>Inhalt</h2>
  <div class="card-list">{''.join(cards)}</div>
</main>
"""
    (OUT / "index.html").write_text(
        page_shell(strip_tags(course["title"]), body, 0, body_class="home-page"),
        encoding="utf-8")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-media", action="store_true")
    args = ap.parse_args()

    data = json.loads(SRC.read_text(encoding="utf-8"))
    course = data["course"]
    built = set(range(len(course["lessons"]))) if args.all else set(LESSONS)

    OUT.mkdir(exist_ok=True)
    (OUT / "lessons").mkdir(exist_ok=True)
    (OUT / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "js").mkdir(parents=True, exist_ok=True)

    print(f"Building {len(built)} lesson(s)")
    for idx in sorted(built):
        fname, n = build_lesson(course, idx, built)
        print(f"  [{idx+1:02d}] {n:3d} blocks -> lessons/{fname}")
    build_index(course, built)
    print("  index.html")

    shutil.copy(STATIC / "course.css", OUT / "assets" / "css" / "course.css")
    shutil.copy(STATIC / "course.js", OUT / "assets" / "js" / "course.js")

    # GitHub Pages runs Jekyll by default, which silently drops files and
    # folders whose names begin with an underscore.
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    if args.no_media:
        print(f"  media: skipped ({len(media_jobs)} referenced)")
    else:
        download_all(media_jobs)
        derive_web(media_jobs)

    # Provenance lives with the masters, not in the published folder: it maps
    # every file back to its original source URL.
    MASTER.mkdir(parents=True, exist_ok=True)
    (MASTER / "manifest.json").write_text(json.dumps(
        {u: {"kind": j["kind"], "file": str(j["master"].relative_to(MASTER))}
         for u, j in sorted(media_jobs.items())},
        ensure_ascii=False, indent=1), encoding="utf-8")

    if cleanup_log:
        seen, uniq = set(), []
        for kind, detail in cleanup_log:
            if (kind, detail) not in seen:
                seen.add((kind, detail))
                uniq.append((kind, detail))
        print(f"\n  editorial cleanups applied ({len(cleanup_log)} total, "
              f"{len(uniq)} distinct):")
        for kind, detail in uniq:
            print(f"    - {kind}: {detail}")

    print(f"\nDone -> {OUT}")


if __name__ == "__main__":
    main()

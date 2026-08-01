# Plan: Static, self-contained archive of the Rise 360 course
## "Reuter: Aus guter Familie (1895)"

Source: `https://rise.articulate.com/share/Jy_b4f_eNXdHGLzBuzs7pE5v40ba_bwR#/`

---

## 0. Headline finding — this is much easier than scraping

**Do not scrape the DOM. The entire course is available as a single JSON document.**

The share page is an empty SPA shell. Its only payload is:

```
window.shareId = "Jy_b4f_eNXdHGLzBuzs7pE5v40ba_bwR";
```

The React runtime then fetches everything from one unauthenticated endpoint:

```
GET https://rise.articulate.com/api/rise-runtime/boot/share/<shareId>
→ 200, 565 KB of JSON
```

That one response contains **all 24 lessons, all 376 blocks, all text, all quiz answers,
all branching-scenario graphs, all media keys, the theme, and the German UI label set.**
A verified copy is already saved at `research/course.json`.

### Consequence for the "progressive loading" problem

Your assumption was that content is fetched on scroll. **It is not.** Everything is in the
DOM-able data from the first request. What you experienced as progressive loading is two
separate, purely client-side features:

1. **`continue` blocks** (61 of them across the course) — a Rise *authoring* feature. The
   author drops a "Weiter" button that hides everything below it until clicked. This is
   the main thing you lost when saving by hand: the saved HTML froze at whatever was
   revealed, and the button lost its handler.
2. **`entranceAnimation: true`** on nearly every block — a fade/slide-in as blocks enter the
   viewport (IntersectionObserver). Cosmetic only.

Both are trivial to reimplement in ~40 lines of vanilla JS. There is no server round-trip
to simulate.

---

## 1. Verified facts about the source

### Course shell
| Field | Value |
|---|---|
| Title | `Reuter: Aus guter Familie (1895)` |
| Accent colour | `#ff631e` |
| `navigationMode` | `free` (learner may jump to any lesson — no gating between lessons) |
| `sidebarMode` | `open` |
| Lessons | 24, all of `type: "blocks"` |
| Label set | German, 427 UI strings under `labelSet.labels` |

⚠️ **`course.lessons[].position` is unreliable** — many are `null` and the non-null ones
have duplicates (three lessons claim `position: 1`). **Use array order**, which matches the
published sidebar order. Do not sort by `position`.

⚠️ **`profile` in the JSON contains the author's real email address.** Strip the `profile`
key from any JSON you ship in the archive.

### Lesson list (array order = sidebar order)

```
 0  Anleitung                                                    4 blocks
 1  1. Dein Bücherregal verrät dich! (30')                      22
 2  2. Was bedeutet Kanon? (15')                                17
 3  3. Schriftstellerinnen im Kanon (30')                       18
 4  4. «Frauenliteratur» – «Männerliteratur»? (15')             19
 5  5. Gabriele Reuter, die Autorin (40')                       29
 6  6. Erziehung, «AgF», S. 1-51 (30')                          20
 7  Zusatzaufgabe: Sprachliche Bilder, «AgF» (20')               5
 8  7. Geschlechterrollen, «AgF» S. 51-103 (40')                13
 9  8. Realismus oder Naturalismus? (40')                       16
10  9. Gesellschaft des Deutschen Kaiserreichs (30')            31
11  10. Frauen in der Kaiserzeit (30')                          20
12  11. Proletariat, «AgF», S. 155-207 (45')                    24
13  Zusatzaufgabe: Männer in der Kaiserzeit (30')                9
14  12. Schlusslektüre, «AgF», S. 207-268 (45')                 19
15  Zusatzaufgabe: Was liest Agathe? (30')                      23
16  13. Rezeption früher und heute (45')                        32
17  14. Muss ich das gelesen haben? (45')                       17
18  15. Abschlussarbeit                                          3
19  Zusatzinformation: Reuters Vorbilder (15')                   7
20  Zusatzinformation: Vergleich mit «Effi Briest» (20')        12
21  Zusatzinformation: «Psychiatrie» (30')                       9
22  Zusatzinformation: Berufsbild Herausgeberin (10')            4
23  Infos für Lehrpersonen                                       3
```

### Complete block inventory (all 376 blocks, whole course)

Every block has the shape
`{ id, family, type, variant, items[], settings{}, background{}, globalBlockId }`.
`family` + `variant` together determine the renderer.

| Count | family | variant | Interactive? |
|---:|---|---|---|
| 61 | `continue` | `continue` | **yes — reveal gate** |
| 60 | `text` | `heading paragraph` | no |
| 40 | `text` | `paragraph` | no |
| 30 | `list` | `checkboxes` | **yes — tickable** |
| 26 | `text` | `heading` | no |
| 21 | `divider` | `divider` | no |
| 20 | `knowledgeCheck` | `multiple response` | **yes** |
| 16 | `knowledgeCheck` | `multiple choice` | **yes** |
| 15 | `multimedia` | `video` | native `<video>` |
| 12 | `impact` | `note` | no |
| 10 | `multimedia` | `audio` | native `<audio>` |
|  8 | `knowledgeCheck` | `matching` | **yes** |
|  6 | `image` | `text aside` | lightbox |
|  5 | `image` | `hero` | lightbox |
|  5 | `interactive` | `scenario` | **yes — branching** |
|  4 | `multimedia` | `attachment` | download link |
|  4 | `interactive` | `process` | **yes — stepper** |
|  4 | `interactive` | `sorting` | **yes — drag/drop** |
|  3 | `quote` | `b` | no |
|  3 | `knowledgeCheck` | `fillin` | **yes** |
|  3 | `flashcard` | `flashcard` | **yes — flip grid** |
|  2 | `list` | `bulleted` | no |
|  2 | `interactive` | `labeledgraphic` | **yes — hotspots** |
|  2 | `image` | `text overlay` | no |
|  2 | `quote` | `carousel` | **yes — slider** |
|  2 | `text` | `subheading paragraph` | no |
|  1 | `interactive` | `timeline` | **yes** |
|  1 | `interactive` | `tabs` | **yes** |
|  1 | `flashcard` | `stack` | **yes — carousel** |
|  1 | `gallery` | `four column` | lightbox |
|  1 | `gallery` | `three column` | lightbox |
|  1 | `quote` | `a` / `c` / `background` (1 each) | no |
|  1 | `impact` | `a` / `d` (1 each) | no |

**That is 22 distinct renderers, 13 of which need JavaScript.** Nothing else exists in the
course — this list is exhaustive and closed. There are **zero `<iframe>` embeds**.

### Media — one resolution rule, verified

Every media object carries a `key`. The URL is always:

```
https://articulateusercontent.com/<key>
```

The `key` is **already URL-encoded** (some contain literal `%2520`). Use it **verbatim** —
do not re-encode or decode it, or the fetch 404s.

Verified working for all four media types plus stock assets:

| Type | Example key prefix | Status |
|---|---|---|
| image | `rise/courses/_-beb.../C-GqiQ73fekoo-HB.jpg` | 200 image/jpeg |
| video | `rise/courses/_-beb.../transcoded-...mp4` | 200 video/mp4 |
| audio | `rise/courses/_-beb.../transcoded-...mp3` | 200 audio/mpeg3 |
| attachment | `rise/courses/_-beb.../...pdf` | 200 application/pdf |
| stock theme art | `assets/rise/assets/themes/classic/...jpg` | 200 image/jpeg |

Image objects may also have `crushedKey` (a smaller re-encode) plus `useCrushedKey: true`.
**Download the full `key`, not the crushed one** — this is an archive; take the best copy.
Keep `crushedKey` downloads too only if you want byte-identical rendering.

Video `poster` and `thumbnail` are absolute `https://images.articulate.com/<transform>/<key>`
URLs — a resizing proxy that will die with the rest. ⚠️ **Do not fetch them as-is**: the
stored transform `f:png,w:1920,s:cover,q:65` returns a **4-bit, 16-colour PNG**. Rewrite the
transform to `f:jpg,w:1920,q:90` for a full-colour frame. This is the only chance to get a
good poster.

### Download budget (measured exactly, whole course = all 24 lessons)

Counting only media actually reachable from content (`items[].media`, `avatar`,
`coverImage`, quote backgrounds) — i.e. **excluding** the vestigial block backgrounds and
`crushedKey` duplicates described above:

| Asset class | Count | Size |
|---|---:|---:|
| video | 15 | **1 345.9 MiB** |
| audio | 12 | 49.8 MiB |
| images | ~67 | 66.1 MiB |
| PDF attachments | 4 | 2.5 MiB |
| **Total** | **98 files** | **1 464 MiB ≈ 1.43 GiB** |

**92% of the payload is 15 video files.** The five largest alone are 934 MiB:

| Size | File |
|---:|---|
| 337.5 MiB | `…lest_das_–_underrated_Klassiker.mp4` |
| 217.4 MiB | `…literaturclub asterix weisse iris.mp4` (lesson 1) |
| 170.4 MiB | `…C0010_1.mp4` |
| 139.0 MiB | `…Ursina Sommer Statement.mp4` |
| 69.8 MiB | `…Kaiserreich – musstewissen Geschichte.mp4` |

If size becomes a problem, re-encoding these to 720p H.264 would cut the archive to a few
hundred MiB. **Recommendation: archive the originals as-is.** Disk is cheap and a
transcode is a lossy decision you cannot undo once the source is gone.

For scale: **lessons 1 + 2 together are only 6 files / 6.4 MiB** — the whole cost is in the
later, video-heavy lessons.

*(An earlier estimate of "~1.7 GiB / 380 files" counted the 211 stock block backgrounds and
71 `crushedKey` duplicates that never render. The 98-file figure above is the one to build
against.)*

### External links

Prose contains hyperlinks to `srf.ch`, `arte.tv`, `nanoo.tv`, `youtube.com`,
`wikipedia.org`, `bpb.de`, `dhm.de`, `dlh.zh.ch`, `orellfuessli.ch`, `hls-dhs-dss.ch`.
These are plain `<a href>` in the HTML, **not embeds**. They are out of scope for
archiving — leave them pointing outward, but see §6.7.

---

## 2. Target architecture

Produce a folder that works from `file://` **and** from any static web server, with no
build step and no network access:

```
reuter-archive/
├── index.html              # cover page + lesson list
├── lessons/
│   ├── 01-anleitung.html
│   ├── 02-dein-buecherregal-verraet-dich.html
│   └── … (24 files)
├── assets/
│   ├── css/course.css
│   ├── js/course.js
│   └── media/
│       ├── img/…  video/…  audio/…  files/…
├── data/
│   └── course.json         # cleaned copy, profile stripped
└── README.md               # provenance + how to open
```

**Decision: pre-render static HTML per lesson, don't ship a client-side renderer.**

Rationale: `file://` + `fetch()` is blocked by CORS in Chrome, so a JSON-driven SPA would
fail on double-click — exactly the failure mode you're trying to escape. Pre-rendered HTML
opens anywhere, is greppable, printable, and survives JS being disabled for the ~60% of
blocks that are static text. `course.json` still ships alongside as the machine-readable
master.

**Generator: a single Python 3 script** (`build.py`, stdlib only). One pass over
`course.json` emitting HTML strings. No npm, no toolchain to rot.

---

## 3. Build steps

### Step 1 — Freeze the source
```bash
curl -s "https://rise.articulate.com/api/rise-runtime/boot/share/Jy_b4f_eNXdHGLzBuzs7pE5v40ba_bwR" \
  -o research/course.json
```
Already done. **Re-fetch once more immediately before the final build**, then never again —
the site is going away. Keep the raw file in version control untouched as the master.

### Step 2 — Mirror all media
Walk `course.json` for every `key` / `crushedKey` / `inputKey`, plus the absolute
`poster` / `thumbnail` / `src` URLs. Download with 8–12 parallel connections, `--continue-at -`
so an interrupted run resumes.

Write a `media-manifest.json` mapping original key → local path → sha256 → byte size.
This is the audit trail that proves the archive is complete.

Sanitise filenames: keys contain `%2520`, spaces, parentheses. Hash-prefix them
(`<sha1(key)[:8]>-<safe-basename>`) to guarantee uniqueness and filesystem safety.

**Verify every download**: any file whose size is 0, or whose bytes begin with `<!DOCTYPE`
or `{"error"`, is a failed fetch masquerading as success. Fail the build loudly on these.

Expected result: **98 files, 1 464 MiB** (see budget table). Download the four 100 MiB+
videos first — they are the longest pole and the most annoying to discover missing later.

### Step 3 — Write the renderers
One function per `(family, variant)` pair from the §1 table. Start with the two lessons you
named, which between them exercise 12 of the 22 renderers.

### Step 4 — Emit HTML, CSS, JS
Per-lesson pages sharing one stylesheet and one script.

### Step 5 — Verify
See §7.

---

## 4. Rendering spec, block by block

### 4.1 Static blocks (no JS)

**`text/*`** — `items[0].heading` and `items[0].paragraph`, both **already HTML strings**
with HTML entities (`&laquo;`, `&ouml;`, `&nbsp;`). Emit them raw; do not escape. Note
`heading` sometimes carries an inline `style="font-size: 32px;"` — keep it.
Variants differ only in which fields are present:
- `heading` → heading only
- `paragraph` → paragraph only
- `heading paragraph`, `subheading paragraph` → both

**`impact/note|a|d`** — same `items[0].paragraph` shape as text, different styling
(a tinted callout box). Used throughout for bibliography notes.

**`quote/a|b|c|background`** — `items[0]`: `paragraph` (the quote HTML), `name` (attribution
HTML), `avatar.media.image.key`, `background.media.image.key`. Variant selects layout;
`background` variant renders the image full-bleed behind the text.

**`divider/divider`** — `items: []`. Emit `<hr>`.

**`image/hero`** — full-width image, optional `caption`.
**`image/text aside`** — image beside `items[0].paragraph`, with `caption` under the image.
**`image/text overlay`** — caption laid over the image.
All three: `settings.zoomOnClick: true` → wire the lightbox (§4.2).

**`gallery/three column|four column`** — grid of `items[].media.image`, each with `caption`.
Lightbox on click.

**`list/bulleted`** — `<ul>` of `items[].paragraph`.

**`multimedia/attachment`** — `items[0].media.attachment` has `filename`, `originalUrl`
(the clean human name), `size`, `mimeType`. Render a download card linking to the local
copy, labelled with `originalUrl`, showing the size.

**`multimedia/video`** — `<video controls preload="metadata" poster="…">`. Local mp4, local
poster. `items[0].caption` is HTML, render below.
**`multimedia/audio`** — `<audio controls>`. Same caption handling.
Both: `duration` (seconds) is available if you want a runtime badge.

### 4.2 Interactive blocks (need JS)

**`continue/continue` — the important one.**
```json
{ "items": [{ "title": "Weiter", "buttonColor": "brand",
              "completeHint": "Complete the content above before moving on." }] }
```
Semantics: everything from this block to the *next* `continue` block (or end of lesson) is
hidden. Clicking reveals that span and scrolls it into view. The button then disappears.

Implementation: at generation time, wrap the blocks into `<section class="reveal-group">`
runs split on `continue` blocks. Group 0 is visible; groups 1..n get `hidden`. The button
for group *n* un-hides group *n+1*.

Add a **"Alles aufklappen"** control in the page header that reveals every group at once.
This is essential for an archive — it makes the page printable and Ctrl-F-able. It is the
single highest-value deviation from the original behaviour.

**`list/checkboxes`** — `items[].paragraph`. Render real `<input type="checkbox">`. In Rise
these are ungraded self-check task lists. Persist state to `localStorage` keyed by block id
so ticks survive a reload.

**`knowledgeCheck/multiple choice`** — `items[0]`: `title` (question HTML), `answers[]` of
`{id, title, correct}`, exactly one `correct: true`; `feedback` (may be `""`).
Radio buttons → "SENDEN" (`labelSet.labels.quizSubmit`) → mark correct/incorrect, show
`feedback` if non-empty, offer retry.

**`knowledgeCheck/multiple response`** — identical but multiple `correct: true`. Checkboxes;
correct only if the selected set matches exactly.

**`knowledgeCheck/fillin`** — `answers[].title` are the accepted strings (several variants,
some 2 chars). Text input; compare case-insensitively and trim-insensitively against every
`answers[].title`. `feedback` is populated here.

**`knowledgeCheck/matching`** — `answers[]` of `{title, matchTitle, correct}`. Left column =
`title` (the statement), right column = `matchTitle` (the person). Render a pool of
draggable chips (one per distinct `matchTitle`, sorted so the pool order gives nothing away)
plus a drop slot on each row. Support click-to-assign alongside dragging — HTML5 DnD is dead
on touch. Dropping onto an occupied slot evicts the sitting chip back to the pool.

⚠️ Chips live *inside* their drop containers, so the chip's own click handler **must**
`stopPropagation()` — otherwise the click bubbles to the container's drop handler, which
instantly re-drops the chip and clears the selection, and nothing can ever be placed.

⚠️ **Ignore the `correct` flag.** It is inherited from the multiple-choice schema and is
meaningless here: in every matching block the rows authored first are `true` and every row
added later is `false`, yet the `false` rows are plainly real pairs. Honouring it would make
7 of lesson 7's 10 pairs unanswerable. Grade on `title ↔ matchTitle` for **every** row.
(Corrected after building lesson 1 — see CLEANUP.md §5.1 for the evidence.)

**`interactive/scenario`** (5×) — the hardest. ⚠️ A response with `action: "tryAgain"` may
also carry a `nextSlide` pointer; the action wins, or a wrong answer silently restarts the
whole scenario. Shape:
```
items[] = scenes, each { id, title, slides[] }
slide  = { id, type:"text", title, description(HTML), emotion,
           goTo:"next"|"slide", nextSlide:{scene,slide}|null, hasCharacter, responses[] }
resp   = { id, description(HTML), action:"continue"|"tryAgain",
           feedback(HTML|null), goTo, nextSlide, emotion }
```
A directed graph. Render as a single container with one `.slide` div per slide, all but the
first `hidden`; response buttons jump by slide id. `goTo:"next"` = next slide in array
order; `goTo:"slide"` = jump to `nextSlide.slide`. `action:"tryAgain"` shows `feedback` and
returns to the same slide. A response with `goTo:"next"` and `nextSlide:null` on the last
slide **ends the scenario**.

`emotion` (`talking`/`thinking`/`happy`/`disappointed`) selects a character illustration.
⚠️ In lesson 2 the scenario has `hasCharacter: true` but **no character image key in the
JSON** — Rise supplies stock character art from its own bundle, which we cannot resolve
from `course.json`. **Decision: drop the character illustration**, render text-only. Note it
in the README. (If you want it, it must be captured separately from a live browser session
before shutdown — see §6.1.)

Also ⚠️ lesson 2's scenario contains **untranslated Rise placeholder text**
("Add feedback here to let learners know they got it right.", "Learners who choose this
response will continue on."). That is in the live course too. **Reproduce it verbatim** —
this is an archive, not an edit.

Rise shows scenarios fullscreen (`family: interactive-fullscreen`). Inline rendering with a
max-width container is acceptable and more archive-friendly; optionally add a
fullscreen toggle via the Fullscreen API.

**`interactive/sorting`** (4×) — `piles[]` of `{id, title}` sits **on the block**, not on the
lesson (`lesson.piles` is empty everywhere — ignore it). `items[]` of `{id, title, pileId}`.
Drag cards into the right pile. Use HTML5 drag-and-drop **plus a click-to-assign fallback**
— DnD is unusable on touch and fiddly under `file://`. Grade against `pileId`.

**`interactive/process`** (4×) — `items[]` of `{title, description(HTML), media, isHidden}`,
up to 8 steps. A numbered stepper with prev/next. ⚠️ Some steps carry
`media.tmp.audio` — a **leftover upload-in-progress object** with `skipProcess` and
`cancelSource` fields and no resolvable final key. Ignore `media.tmp` entirely. Honour
`isHidden: true` by omitting the step.

**`interactive/labeledgraphic`** (2×) — a base image plus `items[]` of
`{x, y, icon, title, description(HTML), isActive}`. `x`/`y` are **percentages**. Absolutely
position markers at `left:x%; top:y%` over the image; click opens a popover. Must stay
correct as the image scales — position within a `position:relative` wrapper sized by the
image itself, never by fixed pixels.

**`interactive/timeline`** (1×) — `items[]` of `{date, title, description(HTML)}`. A simple
vertical timeline is fine and degrades better than Rise's horizontal scroller.

**`interactive/tabs`** (1×) — `items[]` of `{title, description(HTML), media.image}`.
Standard tab panel; add `role="tablist"` / arrow-key nav.

**`flashcard/flashcard`** (3×, grid) and **`flashcard/stack`** (1×, carousel) —
`items[]` of `{front:{media,description}, back:{media,description}}`. CSS 3D flip on click;
for `stack`, prev/next through the cards. Ensure the back face is reachable by keyboard.

**`quote/carousel`** (2×) — `items[]` of quote objects (`paragraph`, `name`, `avatar`,
`background`). Prev/next slider with dots.

### 4.3 Block chrome (applies to every block)

`settings` drives the frame:
- `backgroundType`: `LIGHT` | `TINT` | `ACCENT` | (custom) — `ACCENT` uses course
  `color: #ff631e`.
- `paddingTop` / `paddingBottom`: integers `0–5`, a scale not pixels. Map
  `0→0, 1→16px, 2→32px, 3→48px, 4→72px, 5→96px` and tune against screenshots.
- `entranceAnimation: true` → fade-in via IntersectionObserver. **Must be a no-op when the
  block is inside a still-hidden reveal group**, or blocks animate while invisible and then
  appear already-faded.
- `cardMode: "WHITE"` → white card surface.

⚠️ `block.background.media.image` exists on **almost every block** and points at Rise stock
photos (`assets/rise/assets/themes/classic/cover-image/*.jpg`). These are **vestigial** —
they only render when `backgroundType` selects an image mode, which no block here does.
**Do not download the 211 stock images**; that is over half the image count for zero visual
benefit. Download only keys reachable from `items[].media`, `avatar`, `coverImage`, and
`quote background`. This roughly halves the image payload.

---

## 5. The two named lessons — what to build first

### Lesson 1 · "Dein Bücherregal verrät dich!" (22 blocks)
Exercises: `text/heading paragraph`, `text/paragraph`, `text/heading`,
**`multimedia/audio`**, **`multimedia/video`**, **`knowledgeCheck/matching`**,
`list/checkboxes`, `image/text aside`, `quote/b`, `impact/note`, and
**4 `continue` gates** → 5 reveal groups.

Notable: the video is a 415 s SRF Literaturclub clip (large); the matching block is the one
with the `correct: false` distractor row; the audio block's key contains double-encoded
spaces and parentheses — a good filename-sanitising test case.

### Lesson 2 · "Was bedeutet Kanon?" (17 blocks)
Exercises: `text/paragraph`, **`image/hero`** ×2, `impact/note`,
**`interactive/scenario`** (the branching graph), **`multimedia/attachment`** (a 257 KB PDF),
`divider`, `list/checkboxes`, and **3 `continue` gates** → 4 reveal groups.

Notable: this is the lesson with the placeholder-text and missing-character-art issues
described in §4.2.

Building these two proves out 12 of 22 renderers, both media pipelines, the reveal-group
machinery, and the two hardest interactions. **Get sign-off on these two before generating
the other 22 lessons.**

---

## 6. Difficulties and how each is handled

**6.1 Character art for scenarios is not in the JSON.**
Rise serves stock character SVG/PNG from its own JS bundle. Not resolvable from
`course.json`. → Render scenarios text-only; document the omission. If the art matters,
capture it from a live browser session (DevTools → Network → filter images while stepping
the scenario) **before the site goes offline**. This is the only item with a hard deadline
that `course.json` does not already cover.

**6.2 The site disappearing mid-project.**
`research/course.json` is already frozen, so the *content* is safe regardless. The media is
not. → **Run the Step 2 media mirror now**, ahead of writing any renderer. It is a
~2 GiB, mostly-unattended download and it is the only remaining perishable dependency.

**6.3 Double-encoded keys.**
`%2520` in keys is literal and correct. Passing keys through any encode/decode helper breaks
them. → Treat keys as opaque byte strings; only sanitise when deriving *local* filenames.

**6.4 `file://` restrictions.**
No `fetch()`, no ES modules, no service workers. → Pre-rendered HTML, one classic
`<script>`, no imports. `localStorage` does work under `file://` in Chrome but is shared
across all `file://` pages — namespace keys with a course prefix.

**6.5 Unreliable `position` and empty `lesson.piles`.**
Both are traps that look authoritative. → Use array order; read `piles` off the block.

**6.6 Author PII.**
`course.json` carries the author's email in `profile`. → Strip `profile` from the shipped
`data/course.json`. Decide separately whether the author's name and avatar should remain
visible in the UI (`theme.showAuthor`).

**6.7 External links will rot too.**
Out of the stated scope, but if the archive is meant to last: mark external links visually
and consider recording a Wayback Machine snapshot URL alongside each. Cheap to add, easy to
regret omitting.

**6.8 Copyright.**
The course embeds third-party material (SRF broadcast video, an ARTE reference, press
photos, book covers). A personal offline copy for your own study is a different matter from
republishing. → Keep the archive private; do not deploy it to a public URL. The README
should state this explicitly.

**6.9 Fidelity vs. usability.**
Rise's exact typography and spacing can be approximated but not reproduced bit-for-bit
without lifting their CSS. → Target *functional and visual equivalence*, not pixel parity.
Deliberately improve on the original where it serves archival use: "expand all", real
checkboxes, inline (not fullscreen) interactives, keyboard access throughout.

---

## 7. Verification checklist

Before declaring the archive complete:

- [ ] **Load every page headlessly and assert the console is clean.** One `null`
      dereference aborts the whole script and silently kills every interactive on the
      page — rendering can look perfect while nothing works:
      `chrome --headless --enable-logging=stderr --dump-dom file://… 2>&1 >/dev/null | grep CONSOLE`
- [ ] **Drive the interactions, don't just look at them** — assign a matching quiz and
      submit it, walk each scenario to its end state. Screenshots cannot prove behaviour.
- [ ] Every one of the 376 blocks maps to a renderer — assert on `(family, variant)` and
      **fail the build on an unknown pair**, never silently skip.
- [ ] Block count per lesson in the output matches `len(lesson["items"])`.
- [ ] `media-manifest.json` lists every referenced key; no entry is 0 bytes, HTML, or JSON.
- [ ] `grep -r "articulateusercontent\|images.articulate\|rise.articulate" reuter-archive/
      --include=*.html` returns **nothing** (all media rewritten to local paths).
- [ ] Disconnect from the network, open `index.html` by double-click, and walk all 24
      lessons: no console errors, no broken images, video and audio both play.
- [ ] Every `continue` gate reveals its group; "Alles aufklappen" reveals all.
- [ ] Each of the 47 knowledge-check blocks grades correctly — spot-check one of each of
      the four variants against the live site while it still exists.
- [ ] All 5 scenarios reach an end state and the "do it again" branch loops correctly.
- [ ] Umlauts and «guillemets» render correctly (`<meta charset="utf-8">` everywhere).
- [ ] Print preview of a lesson with everything expanded is legible.

---

## 8. Suggested order of work

1. **Mirror the media now** (§3 Step 2) — the only perishable step. Run it in the
   background while doing everything else.
2. Optionally capture scenario character art from the live site (§6.1) — also perishable.
3. Build `build.py` skeleton: load JSON, iterate lessons, emit shell + sidebar.
4. Implement static renderers (§4.1) — covers ~60% of blocks quickly.
5. Implement reveal groups + expand-all (§4.2 `continue`) — the core fix.
6. Implement lesson 1 and lesson 2 fully; **review with the user**.
7. Implement remaining interactives.
8. Generate all 24 lessons; run §7.

---

## Appendix — files already produced

| Path | What |
|---|---|
| `research/course.json` | Frozen 565 KB source of truth, fetched 2026-07-31 |
| `research/media-keys.tsv` | 378 unique media keys, tab-separated `type<TAB>key` |


---

## 9. Status (updated after the lesson 1 + 2 build)

Built and verified: **`index.html`, lesson 1, lesson 2**. Awaiting review before the
remaining 22 lessons are generated.

Working: `build.py` (stdlib + curl), `static/course.css`, `static/course.js`.
`python3 build.py --all` generates everything; `LESSONS` at the top of `build.py`
controls the subset.

Renderers implemented and visually confirmed: text (3 variants), impact/note, quote/b,
divider, list/checkboxes, image/hero, image/text aside, multimedia video + audio +
attachment, knowledgeCheck/matching, interactive/scenario, continue gates.

Renderers written but **not yet exercised by a built lesson** — verify when the remaining
lessons are generated: gallery, image/text overlay, list/bulleted, quote a/c/carousel/
background, impact a/d, knowledgeCheck multiple choice / multiple response / fillin,
flashcard grid + stack, sorting, process, labeledgraphic, timeline, tabs.

Corrections made to this plan while building: matching `correct` flag (§4.2), video poster
transform (§1), `tryAgain` pointer (§4.2), asset budget (§1).

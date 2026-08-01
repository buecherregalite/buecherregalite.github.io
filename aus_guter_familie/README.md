# Reuter: Aus guter Familie (1895)

A self-contained web version of a course by the same name. The course used to
live on a hosted e-learning platform that was shut down. Its entire content
turned out to be available as a single JSON document, so instead of scraping
pages we froze that JSON and generate a static site from it: plain HTML, no
framework, no tracking, no dependency on the old platform.

Published at **buecherregalite.github.io/aus_guter_familie**.

## Viewing it

Open `index.html` — by double-clicking it locally, or at the published web
address. No server, installation or internet connection is required:
everything the pages need is inside this folder (`lessons/`, `assets/`).

To serve it locally over HTTP instead:

```
python3 -m http.server -d .
```

Tested in Chrome, Safari and Firefox.

## Using it

- The **«Weiter»** buttons reveal the next section.
- **«Alles aufklappen»** at the top of each lesson opens everything at once —
  useful for searching a whole lesson with Ctrl-F, or for printing.
- Quizzes, flashcards, sorting exercises and scenarios all work offline.
  Matching and sorting accept both drag-and-drop and tap-then-tap.
- Ticked checkboxes are remembered by your browser on that computer.
- Text stays readable with JavaScript disabled; only the interactive elements
  need it.

## Layout

| Path | | |
|---|---|---|
| `index.html`, `lessons/`, `assets/`, `.nojekyll` | **published site** | what gets served |
| `media-master/` | keep, **never publish** (gitignored) | full-quality video/audio/image originals + `manifest.json` |
| `research/course.json` | keep, **never publish** (gitignored) | frozen source; the shipped JSON's `profile` key (author PII) has been stripped |
| `build.py`, `static/` | generator | Python stdlib + curl + ffmpeg |
| `tools/` | checks | `verify.py`, `test_widgets.py` |
| `PLAN.md`, `CLEANUP.md` | notes | findings; every deviation from the source |

`media-master/` and `research/` are excluded from git via `.gitignore` — they
are large (1.4 GB, well over GitHub's 100 MB per-file limit) and, in the case
of `research/course.json`, previously carried the author's private email in
its `profile` key. They stay on disk for rebuilding but are never pushed.

## Changing something

Edit `build.py` (structure/renderers) or `static/course.css` / `static/course.js`
(look/behaviour) — never the generated files (`index.html`, `lessons/`,
`assets/`), they get overwritten. Then:

```bash
python3 build.py --all        # regenerate; media is cached, so this is fast
python3 tools/verify.py       # structure, links, size limits
python3 tools/test_widgets.py # drives every quiz/scenario/interactive
```

Both must pass. `build.py` writes straight into this folder (`OUT = ROOT`), so
a rebuild lands in the right place automatically. Then commit and push.

Screenshots are not enough: two questions once rendered perfectly while being
impossible to answer. Always run `test_widgets.py`.

The `.nojekyll` file (repo root) must be kept: without it GitHub silently
discards files whose names begin with an underscore.

## Notes

- Videos are re-encoded for web delivery. The full-quality originals are kept
  separately in `media-master/`, outside the published site.
- Links to outside websites still point to the live internet and will only
  work while those sites exist.
- **Scenario characters removed.** The original showed a cartoon figure with
  an `emotion` per slide; the art was the platform's, not ours, and isn't in
  the data. Text is unaffected.
- **Outbound links rot.** Several external hosts (SRF, ARTE, Wikipedia,
  nanoo.tv, …) are linked from the prose and will break eventually.
- **Two data quirks are worked around, not fixed at source** — matching
  answers' `correct` flag is meaningless, and two questions typed "multiple
  choice" have five correct answers. See `CLEANUP.md` §5 before touching quiz
  rendering.

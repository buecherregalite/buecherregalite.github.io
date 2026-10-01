# Editorial changes made during archiving

Every deviation from the source data is listed here so it can be reviewed and
reverted. The frozen source, `research/course.json`, is never modified.

---

## 1. De-branding

No trace of the original hosting platform remains: no logos, names, fonts,
scripts, analytics, or asset URLs. The archive uses system fonts and its own
CSS/JS. `grep -rE "articulate|rise" reuter-archive/*.html reuter-archive/lessons/`
returns nothing.

*(`data/course.json` is the raw content export and still contains internal
platform field names. It ships as the machine-readable master; it is not served
to a reader. Delete it if that matters to you — the site does not load it.)*

## 2. Untranslated authoring placeholders removed

The live course contained English editor boilerplate in the lesson 2 scenario.
Applied automatically by `build.py`; the substitution tables are at the top of
that file.

| Original | Replaced with |
|---|---|
| `End this scenario.` | `Weiter` |
| `I want to do the scenario again.` | *(whole response removed)* |
| `Learners who choose this response will continue on.` | `Weiter` |
| `Add feedback here to let learners know they got it right.` | *(feedback removed)* |
| `Add helpful feedback here and let learners try again.` | *(feedback removed)* |
| `Learners who choose this incorrect response will be able to try again.` | *(whole response removed)* |

`I want to do the scenario again.` and the last row were dropped entirely
rather than relabelled: both were boilerplate carrying no content (or, for the
"scenario again" response, offered a restart loop rather than a real reply -
see §5 below). Their slides now have a single `Weiter` step.

The build prints every cleanup it applies on each run. If a placeholder appears
in a lesson not yet built, it will be reported then.

## 3. Unsourced quote removed

Lesson 1, "Reflexion" block: a Marcel Reich-Ranicki quote on what a canon is
ended with the plain-text words "bessere Quelle" ("better source") — the
author's own note-to-self to find a proper citation, never resolved before
the course went live. The quote is dropped entirely; the "Reflexion" heading
above it stays. Applied automatically by `build.py` (`DROP_TEXT`), logged on
every build like the placeholder substitutions above.

## 4. Chapter-end link labels standardized

Every lesson ends with a link to the next one. In the source data its label
was whatever the author happened to type for that link, e.g. "Noch nicht
genug?", "Zur Abschlussarbeit", "Mich interessiert auch der Vergleich mit
Effi Briest...", "Hier geht's zum ersten Kapitel...". These are replaced with
one uniform label, "Kapitel N: <Titel>", built from the next lesson's own
title. Bonus lessons (Zusatzaufgabe/Zusatzinformation), whose titles carry no
chapter number, keep their title unchanged rather than being force-numbered.

The lesson footer also used to repeat this as a "Weiter" shortcut on every
page, letting a reader jump to the next chapter without working through the
current one. That shortcut is removed; advancing now only happens through the
labelled link above, which appears once the lesson's content has actually
been worked through.

## 5. Scenario responses redesigned as a chat

Scenarios now render as a conversation: the speaker's line (and any answer
feedback) is a left-aligned "incoming" speech bubble, and response choices are
right-aligned "outgoing" bubbles a reader taps to reply. A step with no real
choice gets a small round `›` button instead of a bubble, since it isn't part
of the dialogue - just a way to move on.

That round button is also why `I want to do the scenario again.` (§2) is
dropped rather than kept as a bubble. In the lesson 2 "Kanon" monologue, every
checkpoint offered exactly two boilerplate responses: `End this scenario.`
(which, despite the name, just moves to the next line - its `goTo` is `next`,
not `end`) and `I want to do the scenario again.` (which jumps back to slide
0). Neither is a real reply; they're the authoring tool's default "continue or
restart" scaffolding, never customized for this monologue. Rendering them as
chat bubbles would have implied a dialogue choice that isn't there. The restart
option is removed, and the remaining `Weiter` collapses to the round button
whenever it is the only response left on a slide - `build.py` asserts its
target agrees with the slide's own fallback target before doing so, so a
future lesson where they diverge fails the build instead of silently
mis-routing.

## 6. Scenario character illustrations dropped

Scenario slides carry `hasCharacter: true` and an `emotion` field, but the
artwork was served from the platform's own bundle and never existed in the
course data. It is omitted. Everything the character *says* is preserved. Per
the course author, these illustrations were third-party assets not covered by
the author's licence, so their removal is intended.

## 7. Entrance animation dropped

Blocks faded in on scroll in the original. Removed deliberately: it is cosmetic,
and implementing it means setting `opacity: 0` by default, which makes text
visibility depend on JavaScript running correctly. For an archive meant to
outlive its toolchain that is the wrong trade. Text now renders with or without
JS.

---

## 8. Three behavioural corrections

These are places where reproducing the raw data literally would have produced a
*worse* result than the original site. All three are judgement calls — flagged
here because they are the ones most likely to warrant a second opinion. Two of
the three are the same underlying lesson: **the data is more reliable than the
labels on it.**

### 8.1 Matching questions: the `correct` flag is ignored

Each matching row has `title`, `matchTitle`, and a boolean `correct`. Reading
`correct` literally makes rows unanswerable. Across the whole course:

| Lesson | rows `true` | rows `false` |
|---|---:|---:|
| 1. Dein Bücherregal | 3 | 1 |
| 5. Gabriele Reuter | 3 | 0 |
| **7. Geschlechterrollen** | **3** | **7** |
| 11. Proletariat | 3 | 5 |
| 13. Rezeption (×3 blocks) | 3 / 3 / 2 | 0 / 0 / 1 |
| 14. Muss ich das gelesen haben? | 3 | 1 |

The pattern: in every block the rows created together (shared id prefix) are
`true`, and every row **added later** (distinct, later id) is `false`. The
`false` rows are plainly legitimate content pairs — e.g. *Onkel Gustav ↔ bewertet
die Schönheit der…*. Lesson 7 would have 7 of 10 pairs unanswerable.

**Conclusion:** `correct` is inherited from the multiple-choice answer schema and
ignored for matching; the platform's editor simply defaults it to `false` on
newly added rows. The archive grades on `title ↔ matchTitle` for every row.

**To revert:** re-add `data-correct` in `r_knowledgecheck()` in `build.py` and
restore the flag check in `course.js`.

### 8.2 Question type is decided by the answers, not the `variant` label

Two blocks are typed `multiple choice` but have **five correct answers each**:

- Lesson 5, *"Gabriele Reuter hat…"* — 5 of 7 answers correct
- Lesson 16, *"Für welche Arten von Text interessiert sich Agathe?"* — 5 of 8

Rendering those as radio buttons, as the label implies, makes them impossible to
answer — you can only ever pick one. The archive therefore counts the correct
answers and uses radios only when exactly one is correct, checkboxes otherwise.
Caught by the interaction tests, not by eye: both rendered perfectly.

**To revert:** restore `typ = "radio" if v == "multiple choice" else "checkbox"`
in `r_knowledgecheck()`.

### 8.3 `tryAgain` responses always return to the same slide

Some scenario responses have `action: "tryAgain"` *and* a `nextSlide` pointer to
a different slide (lesson 2, slide 7 points back to slide 0). Honouring the
pointer would silently restart the whole scenario after a wrong answer. The
action now wins over the pointer: show feedback, then re-ask the same slide.

---

## 9. Video re-encoded for the web

The published site carries 720p H.264 (CRF 23, AAC 128k, faststart) rather than
the 1080p originals — 1346 MB of video becomes roughly a third of that, which is
what makes the site hostable. Audio bitrate is held constant regardless of how
far the picture is compressed, since the spoken word is the content here.

Anything still over 90 MB is re-encoded down a ladder (720p CRF 27 → 540p → 480p
→ 360p) until it fits, so no single file can breach a 100 MB host limit.

**The full-quality originals are not discarded**: they are downloaded once into
`media-master/` alongside a `manifest.json` mapping every file to its source URL.
That folder is the real archive and is not part of the published site.

## 10. Additions not in the original

- **Checkbox state persists** to `localStorage` (namespaced `reuter:`).
- **Scenario responses render as chat bubbles** (§5) — not present in the
  original Rise player.
- **Interactives render inline** rather than fullscreen.
- **Print stylesheet** — expands all gated content, hides navigation.
- **Keyboard access** on tabs, flashcards and scenario buttons.
- **Matching and sorting** use drag-and-drop as in the original, and *also*
  accept tap-a-chip-then-tap-a-row, since HTML5 drag-and-drop does not work on
  touch devices.
- **Link from Psychiatrie to «Berufsbild Herausgeber:in»** — an extra
  chapter-end button (`<div class="gate" data-added>`); `verify.py` leaves
  `data-added` gates out of the block count. That chapter was also renamed
  from «Berufsbild Herausgeberin».
- **Quotation marks unified** to Swiss guillemets «…» (‹…› for a quotation
  inside a non-italic quotation). Italic excerpts are marked as quotations by
  the italics alone, so their outer «…» were dropped; direct speech and titles
  inside them keep «…». Straight quotes ("…", '…'), angle brackets (<…>) and
  German-style »…« used as quotation marks were replaced; apostrophes (geht's,
  Holz') stay. The chapter title «Psychiatrie» lost its quotation marks.
- Author's private email removed from the shipped JSON (`profile` key). The
  contact address published *in* the course content is retained.

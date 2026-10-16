# Chamois

Chamois is a Python application that aims to make state-of-the-art
eye-tracking experiments on reading behavior as easy as possible. The focus
is on stimulus presentation and recording of user responses. It is written
in [Pyglet](https://pyglet.org); the engine (`chamois.py`) doesn't depend on
any particular eye-tracker, and full support for VPixx TRACKPixx3/DATAPixx3
trackers is included (`TPx.py`). The page model, Latin-square
counterbalancing and session-log format are those of the earlier
FreeSimpleGUI version, so existing analysis code keeps working.

**Status:** Chamois is work in progress.  I wrote it for my own lab and share it without any warranty.  It seems to work pretty well, but definitely has some rough edges.  If you’re interested in using it, feel free to contact me to discuss it.

**What changed compared to the FreeSimpleGUI version:**
- **Pyglet** instead of FreeSimpleGUI: one fullscreen window with an
  offscreen framebuffer, no other GUI toolkit.
- **Layout in height units:** font size, spacing, margins and text position
  are fractions of the screen height (1.0 = full height), so an experiment
  looks the same on any screen and resolution.
- **Data in pixels:** word AOIs and gaze samples are saved in screen pixels,
  origin top left, y down (as in the FreeSimpleGUI version and in the
  screenshots). AOIs and gaze can therefore be compared directly; the screen
  resolution is logged with every row.
- **TRACKPixx3 gaze follower:** real-time gaze markers on the experimenter's
  console monitor while the participant's display stays clean (DATAPixx3 M16
  mode); condition codes stamped into every eye sample; mid-session
  recalibration.
- **Dry run:** without a DATAPixx3 the same script runs as a plain reading
  experiment (keyboard-driven, no eye-tracking), so it replaces the
  separate `demo_experiment.py`.

**Key features:** blinking fixation target at trial
start; trial ends when the participant looks at the lower-right corner;
sanity checks of stimuli (words that would not fit stop the experiment
before it starts); Latin square designs with automatic choice of the most
underrepresented list.

**A non-feature:** not designed for timing-sensitive display changes (e.g.
the boundary paradigm).

## Files

| File | What it is for |
| :--- | :--- |
| `demo_experiment_tpx.py` | The experiment: stimuli, page sequence, layout settings. **The file you run.** |
| `chamois.py` | The engine: pages, window, layout, session log, Latin square. Knows nothing about eye trackers. |
| `TPx.py` | The TRACKPixx3/DATAPixx3 layer: gaze recording and markers, condition codes, recalibration, dry run. |
| `setup_once.py` | One-time installer: uv, the dependencies, and VPixx's `pypixxlib`. |
| `aoi_check.py` | Analysis check: draws each trial's AOIs and gaze samples over its screenshot. |
| `pyproject.toml`, `uv.lock`, `.python-version` | Dependency and Python version pinning. |
| `images/` | Screenshots for this README. |

## Running

```bash
python3 setup_once.py              # once per machine (needs internet)
uv run demo_experiment_tpx.py      # every run after that
```

`pypixxlib` is proprietary VPixx software and not on PyPI; `setup_once.py`
downloads it from the [official VPixx site](https://docs.vpixx.com/download)
into `vendor/`. A lab machine kept offline after setup needs
`offline = true` in uv's config (`setup_once.py` explains this at the end).
Developed and tested on Linux with X11.

Calibrate the TRACKPixx3 in LabMaestro first, then run the script.

## Stimuli

Targets come from `stimuli.tsv`, fillers from `fillers.tsv` (in the folder
you run from; four tab-separated columns, no header: item, condition, sentence,
question). A literal `\n` in a sentence starts a new line on screen. Without
the files, small built-in stimuli are used.

```text
1	a	While Bill hunted the deer was hunted by Bill.	Did Bill hunt the deer?
1	b	While Bill hunted the deer that was brown and nimble\nwas hunted by Bill.	Did Bill hunt the deer?
```

## Experiment structure

An experiment is a list of pages shown one by one; each page is one row in
the session log. `build_pages()` in `demo_experiment_tpx.py` has the
complete version; in short:

```python
stimuli = chamois.next_latin_square_list(target_sentences) + fillers
random.shuffle(stimuli)

pages = [chamois.SubjectIDPage(),
         chamois.CenteredInstructions("Welcome to this study!")]
for item, condition, sentence, question in stimuli:
    pages.append(TPx.TPxReadingTrial(item, condition, sentence))
    if random.choice([True, False]):
        pages.append(chamois.YesNoQuestionTrial(item, condition, question))
    pages.append(chamois.Next())
pages.append(chamois.CenteredInstructions("Thank you for your participation!"))
```

Page types: `CenteredInstructions`, `SubjectIDPage`, `TPxReadingTrial`,
`Next` (break) and two kinds of comprehension question:
`YesNoQuestionTrial` (answered with f/j, logged as `yes`/`no`) and
`ComprehensionTrial` (typed answer, confirmed with Enter, logged as typed).
The demo uses yes/no questions; for typed answers replace
`chamois.YesNoQuestionTrial` with `chamois.ComprehensionTrial`, or mix both.
New types: subclass `chamois.Page`.

## Settings

These are safe to change. Sizes are in **height units**: fractions of the
screen height, e.g. 0.03 = 3 % (≈ 32 px on a 1080p screen).

| Setting | Default | What it does |
| :--- | :--- | :--- |
| **`demo_experiment_tpx.py`** | | |
| `STIMULI_BASE`, `FILLERS_BASE` | `"stimuli"`, `"fillers"` | Names of the stimulus files (`.tsv` or `.csv`). |
| `Y_OFFSET` | `0.0` (height units) | Vertical position of the text block's center; 0 = screen center, positive = higher. |
| `ALIGN` | `'left'` | Line alignment: `'left'`, `'center'` or `'right'`. |
| `CROSS_POSITION` | `'left'` | Fixation cross: `'left'` (just before the first word), `'center'` (middle of the text block) or `'right'` (after the first line). |
| `WRAP_WIDTH` | `None` | Automatic line breaks after about this many characters; `None` = off. Manual `\n` breaks are always kept. |
| `WRAP_PRACTICE`, `WRAP_TARGETS`, `WRAP_FILLERS` | `False`, `False`, `True` | Which stimulus groups get automatic line breaks. |
| `practice_sentences` | 2 items | The practice items shown before the experiment. |
| **`chamois.py`** | | |
| `FONT_NAME` | Courier, … | Font; the first one installed is used. A monospaced font keeps `WRAP_WIDTH` exact. |
| `FONTSIZE` | `0.03` (height units) | Font size. |
| `WORDSPACING` | `0.02` (height units) | Gap between words. |
| `LINESPACING` | `0.04` (height units) | Extra space above and below each line. |
| `LEFT_MARGIN` | `0.08` (height units) | Distance of left/right-aligned text from the screen edge (leaves room for a left cross). |
| `BACKGROUND_COLOR`, `TEXT_COLOR`, `HINT_COLOR` | light gray, black, dark gray | Screen colors as (R, G, B). With the DATAPixx3 only grays work (R = G = B, not 100–103); checked at startup. |
| `LINE_DOT_COLOR` | red | Center dot of the fixation cross. |
| `SCREEN_NUMBER` | `0` | Which monitor shows the experiment. |
| `CONTINUE_TEXT`, `YESNO_HINT`, `ANSWER_HINT`, `SUBJECT_ID_PROMPT` | English | Texts the participant sees; edit to translate. |
| **`TPx.py`** | | |
| `TRIGGER_RADIUS` | `0.19` (height units) | Size of the lower-right region that ends a reading trial when looked at. |
| `TRIGGER_DWELL` | `0.08` | Seconds the gaze must stay in that region, so a passing saccade doesn't end the trial. |
| `GAZE_DISPLAY` | `'console'` | Where live gaze markers appear: `'console'` (experimenter only), `'stimulus'` (participant sees them too, in gray) or `'both'`. |
| `GAZE_MARKER` | `'eyes'` | `'eyes'`: one marker per eye (cyan left, magenta right); `'average'`: one marker at the mean of both eyes. Both eyes are always recorded. |
| `MARKER_RADIUS` | `0.01` (height units) | Size of the gaze markers. |
| `STIMULUS_MARKER_GRAY` | `180` | Brightness of participant-visible markers (not 100–103). |
| `SHOW_EYE_IMAGE` | `False` | Keep the DATAPixx3's live eye camera image on the console during trials. |
| `SHOW_DRY_RUN_TAG` | `False` | Dry run only: show the trial's condition code top left, for debugging. |

Everything else (video modes, CLUT indices, shader) belongs to the hardware
setup and should stay as it is.

## Session log

All data goes to `data/`: `logs/`, `screenshots/` and `eyetracking/`. Every
filename starts with participant ID, date/time and Latin-square list, e.g.
`07_2026-07-14_14-59-59_list-a`. The session log (`data/logs/<prefix>_log.tsv`)
has one row per page:

1. `pno`: page number.
2. `type`: page type.
3. `starttime`, 4. `endtime`: seconds since the start of the experiment.
5. `item`, 6. `condition`: of the displayed stimulus.
7. `stimulus`: the displayed text.
8. `response`: the answer, the participant ID, `ABORTED` or `RECALIBRATED`.
9. `screenshot`: the page's screenshot in `data/screenshots/`.
10. `metadata1`: for reading trials, one AOI per word as
    `left,top,right,bottom` in pixels (origin top left, y down).
11. `metadata2`: for reading trials, the eye-tracking file in
    `data/eyetracking/` (gaze in the same pixel coordinates; `32767` = eye
    lost).
12. `screen_width`, 13. `screen_height`: the screen resolution in pixels.

`data/logs/<prefix>_pixel-codes.tsv` decodes the condition stamped into the
eye data's `DigitalOut` column (`DigitalOut >> 16 & 0xFF`).

## Ending a reading trial

1. **Looking at the lower-right corner** (the normal way; region size
   `TRIGGER_RADIUS`, or per trial `TPxReadingTrial(..., trigger_radius=0.25)`).
2. **Space** — fallback when calibration is poor, and the way in dry run.
3. **Escape** aborts the trial (logged as `ABORTED`).
4. **Ctrl+Q** aborts the experiment; the log so far is saved.

On instruction and break screens, **r** suspends the experiment for a
recalibration in LabMaestro. Experimenter keys are never shown on screen.

## Screenshots

Participant ID:
![Participant ID entry](images/screenshot_1.png)

Instructions:
![Welcome screen](images/screenshot_2.png)

Blinking fixation cross at the start of a reading trial:
![Fixation cross](images/screenshot_3.png)

Reading trial (the cross in the lower-right corner is the look target that
ends the trial):
![Reading trial](images/screenshot_4.png)

Comprehension question:
![Yes/no question](images/screenshot_5.png)

Break between trials:
![Break screen](images/screenshot_6.png)

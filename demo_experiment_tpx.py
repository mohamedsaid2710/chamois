# /// script
# requires-python = ">=3.9"
# dependencies = ["pyglet>=2.0", "numpy", "pypixxlib"]
#
# [tool.uv.sources]
# pypixxlib = { path = "vendor/pypixxlib-1.12.1.tar.gz" }
# ///
"""A reading experiment for the TRACKPixx3/DATAPixx3, written in pure
Pyglet. This is the file you run; the machinery sits next to it, one
job per file:

    chamois.py   the engine (pages, log, layout, Latin square);
                 knows nothing about the hardware
    TPx.py       the VPixx layer (M16 shader, gaze, recording)

Flow: participant ID, welcome screen, practice sentences, the
Latin-square-balanced experimental trials with comprehension questions
and breaks, thank-you screen. Every page becomes one row in the
session log; every reading trial additionally saves an eye-tracking
CSV and a screenshot. Everything lands in data/.

How to run
    1. Calibrate the tracker in LabMaestro. This script never
       calibrates on its own; it only warns at startup if no
       calibration exists.
    2. uv run demo_experiment_tpx.py
       (first time on a new machine: python3 setup_once.py)

Stimuli
    Experimental items come from stimuli.tsv, fillers from
    fillers.tsv, both next to this script: four tab-separated columns,
    no header — item number, condition, sentence, question. A literal
    \\n inside a sentence becomes a line break on screen. If a file is
    missing, small built-in stimuli are used instead, so the flow can
    be tested without any files.

No tracker?
    Without a connected DATAPixx3 the experiment runs in dry-run mode:
    normal (non-M16) display, no gaze markers, eye-tracking CSVs with
    only a header row, and reading trials end with space — so it also
    works as a plain reading experiment without eye-tracking. For
    debugging the trial tagging, TPx.SHOW_DRY_RUN_TAG = True draws a
    visible stand-in for the (by design invisible) pixel-mode tag: a
    blue swatch with the condition code in the top left corner.

Keys (experimenter keys are deliberately not shown on screen)
    space   continue / end a reading trial (fallback if the gaze
            trigger fails)
    f / j   answer a comprehension question with no / yes
    r       on instruction and break screens: recalibrate mid-session.
            The window minimizes and normal video mode is restored;
            recalibrate in LabMaestro, return to the experiment
            window, press space to bring the display back, then space
            again to continue.
    Escape  abort the current reading trial (logged as ABORTED)
    Ctrl+Q  abort the whole experiment (a partial log is saved)

    Reading trials normally end on their own, when the participant
    looks at the lower right corner for a moment (see
    TPx.TRIGGER_RADIUS and TPx.TRIGGER_DWELL).
"""

import os
import random
import sys

#import chamois & TPx modules 
import chamois
import TPx

# --------------------------------------------------------------------
# Stimulus files: targets in stimuli.tsv, fillers in fillers.tsv, next
# to this script. Both .tsv and .csv are picked up automatically; if a
# file is missing, the built-in fallback below is used instead.
# --------------------------------------------------------------------

STIMULI_BASE = "stimuli"
FILLERS_BASE = "fillers"

# --------------------------------------------------------------------
# Trial layout: where the text and the blinking fixation cross appear.
# These are handed to every reading trial (the corner look-target that
# ends a trial is not affected — it always sits in the lower right).
#
# Y_OFFSET  vertical position of the text block's center, in height
#           units (1.0 = full screen height), origin at the screen
#           center, y pointing up:
#               0.0 = centered on the screen, 0.15 = a bit above the
#               center, -0.15 = a bit below, 0.3 = clearly up, ...
# ALIGN     horizontal alignment of the lines: 'center', or 'left' /
#           'right' (indented LEFT_MARGIN — set in chamois.py, default
#           0.08 — from the screen edge).
# CROSS_POSITION  where the blinking cross shows: 'center' = middle of
#           the text block (= the screen center while Y_OFFSET is 0),
#           'left' = just before the first word, 'right' = just past
#           the end of the first line.
# --------------------------------------------------------------------

Y_OFFSET = 0.0
ALIGN = 'left'
CROSS_POSITION = 'left'

# --------------------------------------------------------------------
# Automatic line breaking
#
# A manual "\n" in a stimulus is always honored: a sentence that
# already contains one is shown exactly as written, so hand-placed
# breaks in the target items are never disturbed.
#
# Sentences without a manual break can be wrapped automatically, which
# is convenient for fillers, where the break position is not part of
# the design and typing "\n" by hand is tedious. WRAP_WIDTH is the
# maximum number of characters per line; the reading font is
# monospaced, so a character count maps directly to on-screen width.
# Wrapping is greedy: each line takes as many words as fit, and the
# word that would push it past WRAP_WIDTH starts the next line, so a
# line may end a little short but never runs over.
#
# WRAP_WIDTH = None turns the whole feature off (the default). Set a
# character count to enable it, then choose the categories with the
# three flags.


# --------------------------------------------------------------------
WRAP_WIDTH = None       # e.g. 55 wraps to ~55 chars/line; None = off
WRAP_PRACTICE = False   # auto-wrap practice sentences?
WRAP_TARGETS = False    # auto-wrap target items (stimuli.tsv)?
WRAP_FILLERS = True     # auto-wrap fillers (fillers.tsv)?

# Practice items (multi-line), shown before the main experiment:
practice_sentences = [
  [101, "practice", "The weather was wonderful over the weekend. The sun shone without a break and\nit was pleasantly warm. Thomas seized the chance and went for a walk in the\npark. Along the way he met an old schoolfriend he had not seen for many\nyears. They talked for a long time about the past.", "Did Thomas meet an old friend in the park?"],
  [102, "practice", "Julia loves to cook in her free time. Last night she tried out a new recipe\nfrom Italy. She spent two hours in the kitchen preparing the perfect pasta.\nUnfortunately it turned out in the end that she had used far too much salt.\nThe meal was barely edible.", "Was Julia happy with her finished meal?"],
]

# Fallbacks, only used when stimuli.tsv / fillers.tsv are missing:
fallback_target_sentences = [
  [1, "a", "While Bill hunted the deer was hunted by Bill.", "Did Bill hunt the deer?"],
  [1, "b", "While Bill hunted the deer that was brown and nimble was hunted by Bill.", "Did Bill hunt the deer?"],
  [2, "a", "While Mary bathed the baby bathed Mary.", "Did Mary bath the baby?"],
  [2, "b", "While Mary bathed the baby that was small and cute bathed Mary.", "Did Mary bath the baby?"],
  [3, "a", "Anna scolded the chef of the aristocrats who was routinely letting food go to waste.", "Did food go to waste?"],
  [3, "b", "Anna studied with the chef of the aristocrats who was routinely letting food go to waste.", "Did food go to waste?"],
]

fallback_fillers = [
  [20, "filler", "Colorless green ideas sleep furiously.", "Does this sentence make any sense at all?"],
  [21, "filler", "No head injury is too trivial to be ignored.", "Did that sentence make your brain hurt?"],
]


def wrap_sentence(text):
    """Greedy line wrap: words are added to the current line as long
    as the line (including the joining spaces) stays within WRAP_WIDTH
    characters; the first word that would push it past the limit
    starts the next line instead. A line may therefore end shorter
    than WRAP_WIDTH — that is fine, no line ever exceeds it. A single
    word longer than WRAP_WIDTH gets a line of its own, since words
    are never split. Sentences that already contain a manual "\\n"
    come back unchanged, as do one-word sentences. Does nothing when
    WRAP_WIDTH is None."""
    if not WRAP_WIDTH or "\n" in text:
        return text
    words = text.split()
    if len(words) < 2:
        return text
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= WRAP_WIDTH:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def apply_wrapping(rows, enabled):
    """Wrap the sentence column of a stimulus list if `enabled` and
    wrapping is switched on; otherwise return the rows unchanged."""
    if not (enabled and WRAP_WIDTH):
        return rows
    return [[i, c, wrap_sentence(s), q] for i, c, s, q in rows]


def load_or_fallback(base_name, fallback, what):
    filename = None
    for ext in ('.tsv', '.csv'):
        path = base_name + ext
        if os.path.isfile(path):
            filename = path
            break

    if filename is not None:
        print(f"Loading {what} from {filename}")
        return chamois.load_stimuli(filename)
    print(f"No {base_name}.tsv or {base_name}.csv found — using the built-in {what}.")
    return fallback


# --------------------------------------------------------------------
# The page sequence. Calibration happens beforehand in LabMaestro; the
# flow itself never calibrates.
# --------------------------------------------------------------------
def build_pages():
    target_sentences = load_or_fallback(
        STIMULI_BASE, fallback_target_sentences, "target sentences")
    fillers = load_or_fallback(FILLERS_BASE, fallback_fillers, "fillers")

    # Wrap per category; a no-op unless WRAP_WIDTH is set, and manual
    # line breaks are never touched (see wrap_sentence):
    practice = apply_wrapping(practice_sentences, WRAP_PRACTICE)
    target_sentences = apply_wrapping(target_sentences, WRAP_TARGETS)
    fillers = apply_wrapping(fillers, WRAP_FILLERS)

    stimuli = chamois.next_latin_square_list(target_sentences)
    stimuli += fillers
    random.shuffle(stimuli)
    TPx.assign_pixel_codes(
        [row[1] for row in practice] + [row[1] for row in stimuli])

    pages = []
    pages.append(chamois.SubjectIDPage())
    pages.append(chamois.CenteredInstructions("Welcome to this study!"))
    pages.append(chamois.CenteredInstructions(
        "We will begin with a few practice sentences."))
    layout = dict(y_offset=Y_OFFSET, align=ALIGN,
                  cross_position=CROSS_POSITION)
    for i, c, s, q in practice:
        pages.append(TPx.TPxReadingTrial(i, c, s, **layout))
        pages.append(chamois.YesNoQuestionTrial(i, c, q))
        pages.append(chamois.Next())
    pages.append(chamois.CenteredInstructions(
        "Now the main experiment begins. Please concentrate on the "
        "sentences and answer the questions as accurately as possible."))
    for i, c, s, q in stimuli:
        pages.append(TPx.TPxReadingTrial(i, c, s, **layout))
        if random.choice([True, False]):
            pages.append(chamois.YesNoQuestionTrial(i, c, q))
        pages.append(chamois.Next())
    pages.append(chamois.CenteredInstructions(
        "Thank you! The experiment is now complete."))
    return pages


def main():
    chamois.new_session()
    TPx.setup_hardware()
    try:
        app = TPx.TPxExperimentApp(build_pages())
        try:
            app.run()
        except Exception as e:
            if isinstance(e, chamois.ExperimentAbortException):
                print("Experiment aborted.")
            else:
                print("An error occurred.")
            # Whatever was completed up to this point is kept:
            chamois.write_log(app.pages, partial=True)
            if not isinstance(e, chamois.ExperimentAbortException):
                raise
            sys.exit(1)
    finally:
        TPx.shutdown_hardware()


if __name__ == '__main__':
    main()

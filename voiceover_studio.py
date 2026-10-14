
import json
import os
import re
import sys
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
VOICES_DIR = BASE_DIR / "voices"
HISTORY_DIR = BASE_DIR / "history"
HISTORY_FILE = HISTORY_DIR / "history.json"
OUTPUT_FILE = BASE_DIR / "generated_voiceover.wav"

PREVIEW_TEXT = (
    "Hey there! This is a voice preview. "
    "You can use this voice for your next voiceover."
)

PRESETS = {
    "Narration": (1.00, 0.30, "Clear, balanced storytelling"),
    "YouTube": (1.10, 0.18, "Quick, conversational delivery"),
    "Calm": (0.85, 0.60, "Slow, relaxed delivery"),
    "Energetic": (1.20, 0.12, "Fast, punchy delivery"),
}

VOICE_CATALOG = {
    "en_US-joe-medium": {
        "path": "en/en_US/joe/medium",
        "description": "US English • medium quality • about 63 MB",
    },
    "en_GB-cori-high": {
        "path": "en/en_GB/cori/high",
        "description": "UK English • high quality • about 114 MB",
    },
    "en_US-lessac-high": {
        "path": "en/en_US/lessac/high",
        "description": "US English • high quality • about 114 MB",
    },
}

# Additional entries curated from Piper's published voice list. Each model
# is downloaded only when selected in the catalog.
ADDITIONAL_VOICE_MODELS = (
    ("en_GB", "alan", "low", "English (UK)"),
    ("en_GB", "alan", "medium", "English (UK)"),
    ("en_GB", "alba", "medium", "English (UK)"),
    ("en_GB", "aru", "medium", "English (UK)"),
    ("en_GB", "cori", "medium", "English (UK)"),
    ("en_GB", "jenny_dioco", "medium", "English (UK)"),
    ("en_GB", "northern_english_male", "medium", "English (UK)"),
    ("en_GB", "semaine", "medium", "English (UK)"),
    ("en_GB", "southern_english_female", "low", "English (UK)"),
    ("en_GB", "vctk", "medium", "English (UK)"),
    ("en_US", "arctic", "medium", "English (US)"),
    ("en_US", "danny", "low", "English (US)"),
    ("en_US", "hfc_female", "medium", "English (US)"),
    ("en_US", "hfc_male", "medium", "English (US)"),
    ("en_US", "john", "medium", "English (US)"),
    ("en_US", "kathleen", "low", "English (US)"),
    ("en_US", "kristin", "medium", "English (US)"),
    ("en_US", "l2arctic", "medium", "English (US)"),
    ("en_US", "libritts", "high", "English (US)"),
    ("en_US", "libritts_r", "medium", "English (US)"),
    ("en_US", "ljspeech", "medium", "English (US)"),
    ("en_US", "ljspeech", "high", "English (US)"),
    ("en_US", "norman", "medium", "English (US)"),
    ("en_US", "reza_ibrahim", "medium", "English (US)"),
    ("en_US", "ryan", "low", "English (US)"),
    ("en_US", "ryan", "high", "English (US)"),
    ("en_US", "sam", "medium", "English (US)"),
    ("de_DE", "jenny_dioco", "medium", "German"),
    ("de_DE", "thorsten", "medium", "German"),
    ("de_DE", "thorsten", "high", "German"),
    ("de_DE", "thorsten_emotional", "medium", "German"),
    ("es_AR", "daniela", "high", "Spanish (Argentina)"),
    ("es_ES", "davefx", "medium", "Spanish (Spain)"),
    ("es_ES", "sharvard", "medium", "Spanish (Spain)"),
    ("es_MX", "ald", "medium", "Spanish (Mexico)"),
    ("es_MX", "claude", "high", "Spanish (Mexico)"),
    ("fa_IR", "amir", "medium", "Farsi"),
    ("fa_IR", "ganji", "medium", "Farsi"),
    ("fa_IR", "gyro", "medium", "Farsi"),
    ("hi_IN", "pratham", "medium", "Hindi"),
    ("hi_IN", "priyamvada", "medium", "Hindi"),
    ("fr_FR", "siwis", "medium", "French"),
    ("fr_FR", "tom", "medium", "French"),
    ("it_IT", "paola", "medium", "Italian"),
    ("ar_JO", "kareem", "medium", "Arabic (Jordan)"),
    ("ca_ES", "upc_ona", "medium", "Catalan"),
    ("cs_CZ", "jirka", "medium", "Czech"),
    ("da_DK", "talesyntese", "medium", "Danish"),
    ("fi_FI", "harri", "medium", "Finnish"),
    ("is_IS", "salka", "medium", "Icelandic"),
)

for language_code, dataset, quality, language_name in ADDITIONAL_VOICE_MODELS:
    model_name = f"{language_code}-{dataset}-{quality}"
    VOICE_CATALOG[model_name] = {
        "path": (
            f"{language_code.split('_', 1)[0]}/{language_code}/"
            f"{dataset}/{quality}"
        ),
        "description": f"{language_name} • {quality} quality",
    }


# ============================================================
# HELP DOCUMENTATION
# ============================================================

HELP_DOCUMENTATION = {
    "Getting Started": """
GETTING STARTED
===============

Voiceover Studio is a desktop application for creating speech
from text using local Piper text-to-speech models.

FIRST VOICEOVER
---------------
1. Open the Editor page.
2. Type or paste your script.
3. Choose a voice model from Voice Settings.
4. Choose a preset or adjust speed and pause settings.
5. Click Build Sentence Timeline if you want to edit individual
   sentences or their pauses.
6. Click Generate Voiceover.
7. When generation finishes, the audio is saved as:

   D:\\VoiceoverStudio\\generated_voiceover.wav

The app automatically plays the generated audio when possible.

OFFLINE OPERATION
-----------------
Piper runs locally on your computer. Once Python, Piper and the
voice model files are installed, text-to-speech generation does
not require an internet connection.

This application does not need an online account or subscription.
""",

    "Editor and Scripts": """
EDITOR AND SCRIPT MANAGEMENT
============================

SCRIPT EDITOR
-------------
Use the Editor page to write, paste, or revise your script.

The counter below the editor displays:
- Word count
- Character count

BUILD SENTENCE TIMELINE
-----------------------
Click Build Sentence Timeline to split the script into sentence
segments. You can then edit each sentence independently.

Punctuation such as periods, question marks and exclamation marks
helps the application identify sentence boundaries. Abbreviations,
decimal numbers and unusual punctuation may not always split
exactly as intended, so review the timeline.

CLEAR SCRIPT
------------
Click Clear Script to clear the script and sentence timeline.
The application asks for confirmation before clearing.

SAVE SCRIPT
-----------
Use Save Script or Ctrl+S to save the current editor text to a
plain-text .txt file.

OPEN SCRIPT
-----------
Use Open or Ctrl+O to load a plain-text .txt file. Opening a
script replaces the current editor contents and rebuilds the
sentence timeline.

IMPORTANT
---------
The script file and the generated WAV file are separate files.
Saving a script does not generate audio automatically.
""",

    "Sentence Timeline": """
SENTENCE TIMELINE
=================

The Sentence Timeline page gives you control over individual
parts of your voiceover.

CREATE A TIMELINE
-----------------
In the Editor page, click Build Sentence Timeline. The script is
split into sentence segments, using your default pause setting.

SELECT A SENTENCE
-----------------
Click a row in the sentence list. The selected sentence appears
in the editor on the right.

EDIT A SENTENCE
---------------
1. Select the sentence.
2. Change its text in the editing box.
3. Click Apply Sentence Edit.

The main script editor is updated when timeline edits are applied.

ADD A SENTENCE
--------------
Click Add to insert a new sentence after the selected sentence.
If nothing is selected, the sentence is added to the end.

REMOVE A SENTENCE
-----------------
Select a sentence and click Remove.

REORDER SENTENCES
-----------------
Use the Up and Down buttons to move the selected sentence.
The order shown in the timeline is the order used for generation.

APPLY YOUR CHANGES
------------------
Apply Sentence Edit and Apply Pause save changes to the current
timeline. You do not need to rebuild the timeline after every edit.

NOTE
----
The timeline becomes the source of truth for generation once it
has been built. If you make major changes directly in the main
script editor afterward, rebuild the timeline to include them.
""",

    "Pause Control": """
PAUSE CONTROL
=============

DEFAULT PAUSE
-------------
The Default sentence pause slider is in the Editor page.
Its value is used when creating a new sentence timeline and when
adding a new sentence.

INDIVIDUAL PAUSES
-----------------
Each timeline sentence has a pause value.

1. Select a sentence.
2. Adjust the Pause after this sentence slider.
3. Click Apply Pause.

The pause is measured in seconds. The timeline allows values
from 0 to 2 seconds.

HOW PAUSES WORK
---------------
The app generates sentences individually and combines their WAV
files. It inserts silence between adjacent sentences according
to the pause assigned to the preceding sentence.

For example:
- 0.00 seconds: sentences are joined without added silence.
- 0.30 seconds: a short break.
- 1.00 second: a longer dramatic break.
- 2.00 seconds: a substantial pause.

The final sentence's pause does not add silence after the end
of the completed voiceover.

TIPS
----
Use shorter pauses for energetic videos and longer pauses for
calm narration, dramatic reveals, or deliberate storytelling.

Actual perceived pacing also depends on punctuation, voice model
characteristics and speaking speed.
""",

    "Voices and Piper": """
VOICE MODELS AND PIPER
======================

VOICE MODEL FOLDER
------------------
Place Piper voice model files in:

D:\\VoiceoverStudio\\voices

Each model needs both files:
- A .onnx model file
- Its matching .onnx.json configuration file

Example:
en_US-ryan-medium.onnx
en_US-ryan-medium.onnx.json

The names must match. Refresh the voice list after adding or
removing models.

SELECT A VOICE
--------------
Open the Editor page and choose a model from the Voice model
dropdown. The model name does not guarantee a particular accent
or style beyond the information provided by that voice model.

PIPER
-----
Piper is the local text-to-speech engine used by this application.
Generation is started through the Python environment running:

python -m piper

If the command fails, verify that Piper is installed in the same
Python environment used to start Voiceover Studio.

VOICE QUALITY
-------------
Voice quality, pronunciation, naturalness and language support
depend on the selected model. Larger or higher-quality models
may use more memory or take longer to generate audio.

OFFLINE MODELS
--------------
Download model files before going offline. Do not delete model
files while the app is using them.

This application does not download models automatically.
""",

    "Speed and Presets": """
SPEAKING SPEED AND PRESETS
==========================

SPEAKING SPEED
--------------
The speaking-speed slider adjusts the Piper length scale.

Higher values generally produce faster speech. Lower values
generally produce slower speech.

The available range in this application is 0.70x to 1.30x.
Extreme speed changes can affect naturalness and intelligibility.

PRESETS
-------
Narration:
- Speed: 1.00x
- Default pause: 0.30 seconds
- Intended for balanced storytelling.

YouTube:
- Speed: 1.10x
- Default pause: 0.18 seconds
- Intended for a quicker conversational delivery.

Calm:
- Speed: 0.85x
- Default pause: 0.60 seconds
- Intended for slower, relaxed narration.

Energetic:
- Speed: 1.20x
- Default pause: 0.12 seconds
- Intended for fast-paced delivery.

WHAT PRESETS ACTUALLY DO
------------------------
Presets change speed and the default pause. They do not add
genuine emotional acting or guarantee excitement, sadness,
whispering, laughter or other expressive vocal effects.

The selected preset is recorded in generation history.
""",

    "Generate Audio": """
GENERATING AUDIO
================

BEFORE GENERATING
-----------------
- Enter a non-empty script.
- Select a valid voice model.
- Check the sentence timeline if you need custom pauses.
- Ensure there is enough disk space for temporary WAV files
  and the final recording.

GENERATE VOICEOVER
------------------
Click Generate Voiceover or press Ctrl+Enter.

The app generates each sentence separately, then joins the
audio segments with the configured silence between sentences.

PROGRESS
--------
The progress bar tracks completed sentence-generation steps.
Generation time depends on the model, computer performance,
script length and number of sentences.

OUTPUT FILE
-----------
The completed audio is saved to:

D:\\VoiceoverStudio\\generated_voiceover.wav

A successful generation also creates a history entry and stores
a copy of the generated WAV in the history folder.

FORMAT
------
The output is a WAV audio file. WAV files can be imported into
many audio and video editors.

IF GENERATION FAILS
-------------------
Read the error dialog carefully. Common causes include a missing
model, missing Piper installation, an incompatible voice model,
insufficient disk space or a failed subprocess.

The app needs write access to its own folder because it creates
temporary files and saves output there.
""",

    "Preview and Playback": """
VOICE PREVIEW AND PLAYBACK
==========================

PREVIEW VOICE
-------------
Click Preview Voice or press Ctrl+P to generate a short sample
using the currently selected model and speed settings.

Preview uses a built-in sample sentence. It does not use your
entire script.

PLAY OUTPUT
-----------
Click Play or press Ctrl+Space to play the generated output WAV.

STOP
----
Click Stop or press Esc to stop playback. Esc also requests that
an active preview be stopped.

AUDIO REQUIREMENTS
------------------
The app uses pygame's mixer for playback. If generation works
but playback does not, check:
- Windows output device and volume
- Whether another application has exclusive control of audio
- Whether pygame installed correctly
- Whether the WAV file can be played in another audio player

Playback availability can differ from generation availability.
""",

    "Generation History": """
GENERATION HISTORY
==================

The Generation History page lists previous successful generations.

Each entry may show:
- Creation date and time
- Voice model name
- Selected preset
- Number of sentence segments

FILES
-----
History metadata is stored in:

D:\\VoiceoverStudio\\history\\history.json

Copies of generated audio are stored in:

D:\\VoiceoverStudio\\history

LOAD SCRIPT
-----------
Select an entry and click Load Script to restore its script and
sentence segments to the editor and timeline.

RESTORE AUDIO
-------------
Select an entry and click Restore Audio to copy its stored WAV
to the main output path and play it.

DELETE ENTRY
------------
Select an entry and click Delete Entry. Confirm to delete its
history record and its stored audio copy, when available.

IMPORTANT
---------
Deleting a history entry does not intentionally delete the main
generated_voiceover.wav file.

Keep backups of important recordings. History files are stored
locally and can be removed if the application folder is deleted.
""",

    "Keyboard Shortcuts": """
KEYBOARD SHORTCUTS
==================

Ctrl + Enter
Generate the current voiceover.

Ctrl + P
Generate a voice preview.

Ctrl + Space
Play the main output, or stop it if it is already playing.

Esc
Stop audio playback and request that preview generation stop.

Ctrl + S
Open the Save Script dialog.

Ctrl + O
Open a text script.

Ctrl + H
Switch to the Generation History page and refresh the list.

F1
Open the Help & Shortcuts page.

Ctrl + F
Focus the documentation search field.

NOTES
-----
Shortcuts work across the app because they are bound globally.
Some keyboard combinations may behave differently depending on
the active widget or operating system.
""",

    "Files and Folders": """
FILES AND FOLDERS
=================

Main application folder:
D:\\VoiceoverStudio

Main script:
D:\\VoiceoverStudio\\voiceover_studio.py

Voice models:
D:\\VoiceoverStudio\\voices

Main generated WAV:
D:\\VoiceoverStudio\\generated_voiceover.wav

History metadata:
D:\\VoiceoverStudio\\history\\history.json

History WAV copies:
D:\\VoiceoverStudio\\history

TEMPORARY FILES
---------------
During generation, the app creates a temporary working directory
inside the application folder. It also creates temporary WAV files
for intermediate sentences and preview audio.

The app attempts to remove temporary generation files when work
finishes. If the app or computer is forcibly terminated, a
temporary file may remain and can usually be removed after
checking that the app is closed.

BACKUPS
-------
Back up scripts, final WAV recordings, important history audio
and any voice models you need to preserve.

The application does not synchronize files to the cloud.
""",

    "Troubleshooting": """
TROUBLESHOOTING
===============

NO VOICE MODELS FOUND
---------------------
1. Check that models are inside the voices folder.
2. Check that each .onnx file has a matching .onnx.json file.
3. Click Refresh in Voice Settings.
4. Confirm that the files are not inside an extra nested folder.

PIPER MODULE NOT FOUND
----------------------
Open PowerShell in the app folder and run:

python -m pip show piper-tts

If it is not installed, install Piper into the same Python
environment used to run the application:

python -m pip install piper-tts

Use the Python executable that actually launches the app.

GENERATION FAILS
----------------
- Confirm the model file exists.
- Confirm its JSON file matches its name.
- Read the full error message from Piper.
- Check available disk space and folder permissions.
- Try generating a short script.
- Try another installed voice model.

NO AUDIO OR PLAYBACK ERROR
--------------------------
Check the Windows audio output, volume and pygame installation.
Try opening generated_voiceover.wav with another audio player.

SCRIPT OR TIMELINE LOOKS OUT OF DATE
------------------------------------
If you edit the main script after building the timeline, build
the timeline again so it reflects the new text.

HISTORY AUDIO IS MISSING
------------------------
A history entry may point to an audio file that was moved or
deleted. Restoring audio requires that stored file to exist.

PYTHON ERRORS
-------------
Launch the application from PowerShell so diagnostic messages
remain visible:

cd D:\\VoiceoverStudio
python .\\voiceover_studio.py

Copy the complete traceback when asking for help. The last
lines often identify the error, but earlier lines can also
provide useful context.

INSTALLATION CHECK
------------------
Check Python:

python --version

Check Piper:

python -m pip show piper-tts

Check pygame:

python -m pip show pygame

Package installation requires internet access unless the
packages are already available locally.
""",

    "Technical Overview": """
TECHNICAL OVERVIEW
==================

USER INTERFACE
--------------
The graphical interface is built with PySide6.
The editor, sentence timeline, history and help content are
organized into dedicated workspace pages.

TEXT-TO-SPEECH
-------------
The application launches Piper as a subprocess using the current
Python interpreter. Script text is sent to Piper through stdin.

SENTENCE PROCESSING
-------------------
The script is divided into sentence segments. Each segment is
generated to a temporary WAV file. The app then combines the WAV
files and inserts silence between segments.

AUDIO
-----
The wave module reads and writes PCM WAV data. Sentence audio
must use compatible sample rates, channel counts, sample widths
and uncompressed formats to be combined safely.

PLAYBACK
--------
pygame.mixer handles audio playback.

THREADING
---------
Generation and preview run in background threads so the PySide6
interface can continue responding. A queue communicates progress
and completion events back to the interface thread.

HISTORY
-------
The history is stored as JSON, while WAV copies are kept as
separate local files. The JSON records refer to these audio files.

PRIVACY AND NETWORK
-------------------
This app is designed for local processing. It does not need a
cloud TTS account. Piper and the selected model run on your
computer. Python package installation or model downloading may
require internet access before offline use.

LIMITATIONS
-----------
- Voice expressiveness depends on the model.
- Automatic sentence splitting is not perfect.
- Speech generation speed depends on hardware and model size.
- The application is a desktop utility, not a full multitrack
  digital audio workstation.
""",
}


# ============================================================
# HELPERS
# ============================================================

def split_sentences(text):
    """Split text into sentence-sized chunks without losing punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.findall(r".+?(?:[.!?]+(?=\s|$)|$)", text)
    return [part.strip() for part in parts if part.strip()]


def read_history():
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        pass
    return []


def write_history(entries):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    temp = HISTORY_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temp, HISTORY_FILE)


# ============================================================
# APPLICATION
# ============================================================


if __name__ == "__main__":
    from voiceover_studio_qt import main

    raise SystemExit(main())



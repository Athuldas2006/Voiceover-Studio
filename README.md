<div align="center">

# Voiceover Studio

### Turn a script into a polished voiceover.

An offline-first Windows desktop app for writing, voicing, and reviewing narration with [Piper](https://github.com/OHF-Voice/piper1-gpl).

[Features](#features) · [Get started](#get-started) · [Build the Windows app](#build-the-windows-app) · [Keyboard shortcuts](#keyboard-shortcuts)

</div>

---

## Make your script sound ready

Write or import a script, choose a Piper voice, and generate speech on your computer. Build a sentence timeline to edit individual lines and shape the pauses. Preview voices, adjust delivery, and revisit earlier generations from the history panel.

Voice generation runs locally after you have downloaded a voice model. Internet access is needed to download models; model files are not included in this repository.

## Features

- **Local Piper text to speech** with downloadable voice models
- **Script editor** with open, save, undo, and redo
- **Sentence timeline** for editing segments and setting pauses
- **Voice previews** and controls for speaking speed and style
- **Playback controls** for generated narration
- **Generation history** for finding previous work
- **Windows desktop interface** built with PySide6

## Get started

### Requirements

- Windows 10 or later
- Python 3.13 (64-bit recommended)

### Run from source

```powershell
python -m pip install -r requirements.txt
python voiceover_studio.py
```

Open **Browse and Download More Voices** in the app to install a voice model. Piper voice models have their own licenses; review a model's license before using it in a project.

## Build the Windows app

Run the included build script from PowerShell:

```powershell
.\build_windows.bat
```

The script installs the Python requirements and creates an onedir build at `dist\Voiceover Studio\Voiceover Studio.exe`. Keep the complete output folder together. Voice models are downloaded separately from inside the app.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+Enter` | Generate voiceover |
| `Ctrl+P` | Preview voice |
| `Ctrl+Space` | Play or pause output |
| `Ctrl+S` | Save script |
| `Ctrl+O` | Open script |
| `Ctrl+H` | Open generation history |
| `Ctrl+F` | Search help |
| `F1` | Open help |
| `Esc` | Stop playback |

## Project files

- `voiceover_studio.py` — application entry point and core configuration
- `voiceover_studio_qt.py` — PySide6 desktop interface
- `requirements.txt` — Python dependencies
- `build_windows.bat` — Windows executable build script
- `assets/voiceover_studio.ico` — application icon

## License

No project license has been specified yet. Voiceover Studio's source and Piper voice models may have separate licensing terms.


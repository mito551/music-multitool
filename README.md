# Music Multitool

One window for the chores around a piece of music: split a song into stems, turn audio into MIDI, get the lyrics, read
a scanned score, find the tempo and key, convert and trim. Add files, press Run, and everything is queued and processed
one after another, with the results sorted into a folder per song.

It runs on Linux (one AppImage) and Windows (one exe). Nothing heavy is installed up front: the app tells you what each
feature does and how much disk it takes, and installs only what you choose.

> **Disclaimer:** this app was developed with Claude Sonnet 5.5, an AI model from Anthropic. It has tests, but much of it
> has only been exercised on Linux, and the Windows build has not been tried on a real Windows machine. Check results
> that matter, and report problems in the issue tracker.

## Download

Get the latest files from the [Releases](https://github.com/mito551/music-multitool/releases) page.

- **Windows:** `MusicMultitool.exe`. Keep it anywhere and double-click it. Nothing else to install.
- **Linux:** `MusicMultitool-x86_64.AppImage`. Make it executable (`chmod +x`) and run it. See
  [Dependencies](#dependencies) for the few system packages it uses.

On first start the app opens **Settings → Components**. Pick the features you want, check the sizes, press **Install
selected**. You can come back any time to add more.

## What it does

**Convert / Trim.** Converts to WAV, FLAC, MP3, ALAC or M4A. Optionally changes the sample rate (22.05 to 48 kHz) and
channel count, normalises loudness to a target level (default −14 LUFS), trims silence at the start and end, or cuts a
section by start and end time.

**Separate.** Splits a song into vocals, drums, bass and other, or just the one stem you want, using demucs. You can
choose the model (`htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `mdx_extra`), the number of shifts (more is slower and
slightly better) and the output format.

**Transcribe.** Turns audio into a MIDI file with dettato; pitched instruments and drums come out as separate
tracks. Run it after Separate to transcribe each stem on its own (the *Stems → MIDI* chain does exactly that).

**Lyrics.** Writes the lyrics of a song with timestamps as `.srt`, `.lrc` and plain `.txt`, using Whisper. Pick the
model size (tiny to large-v3), or leave the language on auto.
*SynthV lyrics:* turn on the option and the app also writes `<song>.synthv.txt`, the words spread over the notes of the
song's vocal MIDI: the first note carries the word, `+` is the next syllable on a new note, `-` continues the previous
syllable on a new note. Run Transcribe on the vocals first, or pick a MIDI file yourself. Drop a `.synthv.txt` on the
Lyrics tab, with the original `.txt` next to it, to get clean lyrics back with the original line breaks.

**Scan score.** Reads scanned sheet music, images or PDFs, into MusicXML with copisteria, one file per page. Choose
the detector size (28m is the default, 2m is smaller) and which PDF pages to read (`all`, `3`, `2-5`).

**BPM and key.** The *Detect BPM & key…* button in the sidebar analyses one file in a few seconds and shows tempo and
key. Under it sits a tap-tempo pad: tap the button, or press Space anywhere in the window, and it shows your tempo next
to the detected one and says whether they match, or one is half or double the other.

**Chains.** A chain runs several tools in order, each step taking what the previous one made. Built in:

- *Clean → Separate:* convert, then split into stems
- *Stems → MIDI:* split into stems, then transcribe every stem
- *Vocals → Lyrics:* split off the vocals, then transcribe the lyrics
- *Full breakdown:* convert, analyse, split, then MIDI for each stem

Build your own on the Chains tab: add steps, choose each step's tool and which earlier result it reads, set its options,
and save it under a name. Your own chains can be deleted again; the built-in ones can't.

### The queue

Add files with *Add files…* and *Add folder…* in the sidebar, or drag them onto the window. Each file becomes a queue
item for the tool you are on. **Run** processes them one at a time; **Cancel** stops the current one; **Retry failed**
and **Clear done** do what they say. The pencil on an item sets options for just that file, and the folder button
opens its results. With **Skip existing** on, anything already done is not redone.

Results go to the output folder (default `~/Music/music-multitool`, change it at the bottom right), one folder per song:

    <output folder>/<song>/stems/  midi/  lyrics/  audio/  analysis/  score/

The same file run through several tools lands in the same song folder.

### Settings

- **Components:** what is installed, what each part does, how big it is, and the install button.
- **General:** output folder, skip existing, default device (auto, GPU or CPU), and which interface to use.
- **Repos:** where demucs, dettato and copisteria come from (see below).
- **Models:** the sheet-music scan's model weights, with a download button for each.
- **Paths:** use your own Python for the processing, add folders with ffmpeg or poppler, see what was found, and
  **Delete…** to remove everything the app downloaded (optionally your settings too).

## Components and disk space

Sizes are approximate disk use; downloads are smaller. Whisper and the other models download the first time you use
them.

| Component | What it adds | Disk |
|---|---|---|
| Convert / Trim | the small processing environment (uses ffmpeg) | 20 MB |
| BPM & key detection | librosa and friends | 400 MB |
| Stem separation | demucs (model weights 80–400 MB on first use) | 120 MB |
| Audio to MIDI | dettato (model weights on first use) | 250 MB |
| Lyrics | faster-whisper (model 75 MB to 3 GB on first use) | 250 MB |
| Sheet-music scan | copisteria (+130 MB of weights) | 350 MB |
| PyTorch, shared by separation, MIDI and scanning | CUDA build with an NVIDIA GPU: about 6.5 GB (Linux) or 4.5 GB (Windows); CPU-only: about 0.7 GB | see left |
| CUDA libraries for Lyrics | only with an NVIDIA GPU | 1.5 GB |
| ffmpeg (Windows only, if not found) | | 280 MB |

With an NVIDIA GPU, the **Use the NVIDIA GPU** switch decides between the large CUDA build and the small CPU build. The
CPU build works everywhere, just more slowly.

## Dependencies

**What you need on your system**

| | Linux (AppImage) | Windows (exe) |
|---|---|---|
| FUSE 2, to run AppImages | `fuse-libs` (Fedora), `libfuse2` (Debian, Ubuntu); or run with `--appimage-extract-and-run` | – |
| ffmpeg, with the MP3 encoder | from your distribution (on Fedora from RPM Fusion) | downloaded for you if missing |
| poppler, for scanning PDFs | `poppler-utils` | downloaded for you if missing |
| X11 cursor library, for the bundled Qt interface | `xcb-util-cursor` (Fedora), `libxcb-cursor0` (Debian, Ubuntu) | – |
| NVIDIA driver, for GPU use | optional | optional |

On Fedora: `sudo dnf install fuse-libs poppler-utils xcb-util-cursor` plus ffmpeg from RPM Fusion.
On Debian and Ubuntu: `sudo apt install libfuse2 ffmpeg poppler-utils libxcb-cursor0`.

On GNOME and similar desktops the AppImage uses your system's GTK4 and libadwaita (1.5 or newer) for a native look, if
`python3-gobject`, `gtk4` and `libadwaita` are installed; otherwise, and on KDE, it uses its bundled Qt interface. You
can force one in Settings → General or with `--ui gtk` or `--ui qt`.

**What the app downloads when you ask for it**

PyTorch, faster-whisper, librosa and their libraries from PyPI, into a private Python environment. On Windows (and in the
Qt part of the AppImage) it also fetches [uv](https://github.com/astral-sh/uv), which brings a Python 3.12 along.

**The projects it wraps**

The three tools below are not bundled. In **Settings → Repos** give each a local folder or a git URL, then install the
component; URLs are cloned for you.

- demucs, stem separation: <https://github.com/adefossez/demucs>
- dettato, audio to MIDI: <https://github.com/kobimusic/dettato>
- copisteria, score scanning: <https://github.com/kobimusic/copisteria>

Without a repo set, that tool simply stays unavailable; the others keep working.

## Where things are stored

| | Linux | Windows |
|---|---|---|
| Settings and your chains | `~/.config/music-multitool/` | `%APPDATA%\MusicMultitool\` |
| Downloaded environment, repos, tools | `~/.local/share/music-multitool/` | `%LOCALAPPDATA%\MusicMultitool\` |

Settings → Paths → Delete… removes the second one (and, if you tick it, the first). Deleting the app itself is just
deleting the file.

## License

GPL-3.0, see [LICENSE](LICENSE). The release builds bundle Qt through PySide6, which is LGPL-3.0.

---

# For developers

## Run from source

    git clone https://github.com/mito551/music-multitool && cd music-multitool
    python3 -m venv .venv && .venv/bin/pip install -e . pytest PySide6
    PYTHONPATH=src python3 -m musicmultitool [--ui gtk|qt] [--smoke]

The GTK interface needs the system's PyGObject, GTK4 and libadwaita 1.5+ (`python3-gobject gtk4 libadwaita`), so run it
with the system Python. The Qt interface needs only `PySide6`. For a launcher entry in your desktop, run
`music-multitool --install-desktop` after `pip install -e .`.

## Tests

    python -m pytest              # fast tests, no models
    python -m pytest -m slow      # also the tests that load real models (needs the worker environment)

The Qt tests are skipped when PySide6 is not installed and run headless (`QT_QPA_PLATFORM=offscreen`).

## How it is built

Two processes. The **UI** (GTK or Qt, `ui/` and `qt/`) is pure Python on the system interpreter. The **worker**
(`worker/`) runs in a separate environment that holds torch and friends, and speaks JSON lines on stdin and stdout with
the UI; cancelling a job kills the worker. All logic that is not widgets lives in `core/` and is shared by both
interfaces: the queue, the batch runner (chains, skip-existing, song folders), presets, settings, the component table
and the setup plan.

- **Tools** are modules in `worker/kinds/`, each with `run(job, emit) -> (outputs, result)` and an optional
  `release()`, imported lazily and listed in `worker/registry.py`. A tool's form lives in `ui/tabs/` and `qt/tabs.py`,
  its facts in `core/tools.py`.
- **Roles** tag outputs (`stem:vocals`, `midi`, `lyrics`, `audio`, `analysis`, `score`); chain steps select inputs by
  role.
- **The worker environment** is built by `core/setup_env.plan()` from the chosen components in `core/components.py`.
  `core/provision.py` downloads uv, ffmpeg and poppler on Windows and keeps the worker's copy of the package when the app
  is a frozen build.
- **Interface choice** is in `launch.py`: `--ui`, then the setting, then the desktop (`XDG_CURRENT_DESKTOP`; Qt on
  KDE-like desktops and off Linux), falling back to whichever toolkit is installed.

To add a tool: write the `worker/kinds/` module, register it, add its tab in both `ui/tabs/` and `qt/tabs.py`, and add a
`Component` entry if it needs something installed.

## Releases

Pushing a tag `v*` runs `.github/workflows/build.yml`: it builds `MusicMultitool.exe` on Windows (PyInstaller, one
file) and `MusicMultitool-x86_64.AppImage` on Ubuntu 22.04 (`packaging/appimage.sh`), then attaches both to a GitHub
Release. Both can also be built locally:

    pyinstaller --noconfirm packaging/musicmultitool.spec        # one-file exe, Qt only
    packaging/appimage.sh                                        # needs pyinstaller and PySide6 in the active Python

The frozen builds ship the app's plain-Python source as data, because the worker is a separate Python that imports it.
The AppImage's `AppRun` starts the GTK interface from system Python when GTK4 and libadwaita 1.5+ are present and the
bundled Qt build otherwise.

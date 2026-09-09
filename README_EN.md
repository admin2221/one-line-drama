<p align="center">
  <img src="assets/brand/hero-wide.png" alt="Drama Factory" width="820">
</p>

<h1 align="center">Drama Factory · 短剧工厂</h1>

<p align="center"><strong>Describe a story in one sentence — get a complete vertical short drama.</strong> (ComfyUI + MiniMax H3)</p>

<p align="center">
  <a href="https://admin2221.github.io/one-line-drama"><img src="https://img.shields.io/badge/Website-Drama%20Factory-ffb84d?style=for-the-badge" alt="Website"></a>
  <a href="https://github.com/admin2221/one-line-drama"><img src="https://img.shields.io/badge/中文版-README-4f7cff?style=for-the-badge" alt="中文 README"></a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776ab.svg" alt="Python"></a>
  <a href=""><img src="https://img.shields.io/badge/Platform-Windows-0078d4.svg" alt="Windows"></a>
</p>

<p align="center">
  <a href="#showcase">Showcase</a> &nbsp;·&nbsp;
  <a href="#how-it-works">How It Works</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="#windows-installer">Windows Installer</a> &nbsp;·&nbsp;
  <a href="#contact">Contact</a> &nbsp;·&nbsp;
  <a href="#license">License</a>
</p>

---

Drama Factory turns "write a story" into "type one sentence". It compresses the hundreds of production steps — script directing, character design, shot-by-shot vertical video generation and concatenation — into a single pipeline driven by ComfyUI.

> ✅ Fully open source: **no activation code, no trial gate, no watermark**. MIT licensed.

---

## Showcase <a id="showcase"></a>

Real output clips generated from a one-sentence prompt (click a poster to play the mp4; online player on the [official site](https://admin2221.github.io/one-line-drama)):

<table>
<tr>
<td align="center" width="33%"><a href="assets/showcase/demo1.mp4"><img src="assets/showcase/demo1-poster.jpg" width="230" alt="The Adventures of Xio Niu"></a><br><sub><b>The Adventures of the Snail</b><br>3D adventure · rescue at the waterhole</sub></td>
<td align="center" width="33%"><a href="assets/showcase/demo2.mp4"><img src="assets/showcase/demo2-poster.jpg" width="230" alt="African Elephant"></a><br><sub><b>Little Elephant</b><br>family warmth · playing at the waterhole</sub></td>
<td align="center" width="33%"><a href="assets/showcase/demo3.mp4"><img src="assets/showcase/demo3-poster.jpg" width="230" alt="The Way Home"></a><br><sub><b>The Way Home · Runze Lodge</b><br>return to the village · heirloom seal</sub></td>
</tr>
</table>

---

## How It Works <a id="how-it-works"></a>

```
One-sentence plot
   │  ① LLM script director (local Qwen3.5-9B, or any OpenAI-compatible cloud API)
   │     → character sheet + N shot script JSON
   ▼
   │  ② LLM visual concept designer → Z-Image generates the character reference image
   ▼
   │  ③ Shot-by-shot MiniMax H3 ref2va vertical video (shared reference image + native audio)
   ▼
   │  ④ ffmpeg concatenation → final_drama.mp4
```

- **Character consistency** — every shot shares one reference image (`<Picture 1>` / `ref_image_0`)
- **Unlimited length** — shot count is decided by the script (`--target-seconds 90+` auto-expands into acts); each shot is generated independently with resume support
- **VRAM friendly** — one shot at a time then VRAM is released (works on 16 GB GPUs)

---

## Quick Start (from source) <a id="quick-start"></a>

Prerequisites: a running ComfyUI at `http://127.0.0.1:8188` with the required custom nodes/models
(MiniMax H3 ref2va, Z-Image turbo, ComfyUI-llama-cpp_vlm; 16 GB VRAM recommended).

```bat
git clone https://github.com/admin2221/one-line-drama.git
cd comfyui
python -m pip install -r requirements.txt

:: one sentence → full video
python factory\drama_factory.py "A down-and-out scholar finds an ancient mirror that lets him travel through time..."

:: resume skipped shots
python factory\drama_factory.py "your story..." --resume

:: reuse an existing script JSON (skip the LLM stage)
python factory\drama_factory.py --script-json output\xxx\script.json

:: graphical interface
python gui\drama_gui.py
```

> `providers.json` (may contain real API keys) is **not** in the repo — copy `providers.example.json` and fill it in yourself.

### Key options

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` | `http://127.0.0.1:8188` | ComfyUI endpoint |
| `--llm` | `qwen3.5` | script LLM: `qwen3.5/qwen3.8/qwen3.8ag/custom` |
| `--steps` | `16` | H3 sampling steps |
| `--megapixels` | `0.4` | H3 resolution (0.4 ≈ 480×864 portrait) |
| `--aspect` | `9:16 (Portrait)` | aspect ratio |
| `--resume` | off | skip already generated shots |
| `--script-json` | — | reuse a script JSON |
| `--target-seconds` | — | target length in seconds; ≥90s auto-expands into acts |
| `--review` | off | AI review/revise the script once (needs provider) |
| `--yes` | off | skip script preview confirmation |
| `--plan-only` | off | only write the script, do not render |
| `--tts` | off | character narration via edge-tts |
| `--output` | `output/<timestamp>` | output directory |

---

## Windows One-Click Installer <a id="windows-installer"></a>

The `release/` folder ships a ready-to-use installer — no Python or source needed:

```
release/
├── 短剧生成器安装向导.exe      # double-click to install (GUI + CLI engine)
└── InstallFiles/
    ├── drama-gui.exe
    ├── drama-cli-onefile.exe
    ├── 使用说明.txt
    └── drama_icon.png
```

- End-user illustrated tutorial (Chinese): `docs/安装使用图文教程.md` (a single-file HTML copy with embedded images lives next to it — ready to send to customers)
- The wizard installs into `%LOCALAPPDATA%\Programs\短剧生成器` (optional desktop shortcut)
- Build your own installer: `python -m pip install -r requirements.txt pyinstaller` then `powershell -ExecutionPolicy Bypass -File .\build_release.ps1`

---

## Repository Layout

```
factory/          four-stage CLI engine (director, client, concat, provider, prompts)
gui/              tkinter GUI (script review / AI revise / parameter panel)
deploy/           Tk install wizard + user manual
characters/presets/  preset character JSONs
workflows/        reference ComfyUI workflow JSONs
assets/           brand images, showcase videos, icons
docs/             GitHub Pages site + illustrated tutorial
release/          latest open-source Windows installer
```

---

## Tech Notes

- **Reference image**: `MiniMaxH3ReferenceToVideo.ref_images.ref_image_0` maps to `<Picture 1>` in the prompt (1-based). The character image is uploaded via `/upload/image` and loaded with `LoadImage` per shot.
- **Frame math**: `seconds → round(dur*24) → snapped to the 17k+5 grid` (H3 length constraint; 124 frames ≈ 5 s).
- **LLM text capture**: LLM output goes through `ShowText|pysssss` into history, extracted by `client.first_text()`.
- Falls back to a built-in H3 ref2va node graph when no workflow JSON is found.

## Requirements & Hardware

| Component | Notes |
|---|---|
| ComfyUI | `http://127.0.0.1:8188` (verified on 0.30.x) |
| ComfyUI-llama-cpp_vlm | local script/visual LLM (Qwen3.5-9B GGUF etc.) |
| MiniMax H3 (ref2va) | video + native audio |
| Z-Image turbo | character reference images |
| ffmpeg | concatenation (on PATH or auto-detected) |
| Python | ≥3.10 (source/build only; the exe ships its own runtime) |

- **16 GB VRAM** (RTX 4060 Ti class) is enough.

---

## Contact <a id="contact"></a>

Questions, feedback, or collaboration? Reach the author:

- **QQ**: `461765077` ([start a quick QQ chat](https://wpa.qq.com/msgrd?v=3&uin=461765077&site=qq&menu=yes))
- **WeChat**: `wyq-kf` (please note “Drama Factory” when adding)
- **Repository**: [github.com/admin2221/one-line-drama](https://github.com/admin2221/one-line-drama)

---

## License <a id="license"></a>

[MIT](./LICENSE). Third-party models (MiniMax H3 / Z-Image / Qwen) follow their own licenses.

> README layout inspired by [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage).
> Fully open source — no activation code, no trial gate. Historical commercial/gated code has been purged from the git history.

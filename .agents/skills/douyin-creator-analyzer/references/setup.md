# First-run setup

The GitHub installation includes the Python tools, report templates, and dependency lockfile. The first `uv run --locked` provisions the Python environment. Rendering an existing evidence bundle only needs this environment. Video processing uses FFmpeg and ffprobe. Reuse any existing timestamped transcript, or configure whisper-cli and a local model for transcription.

Reuse the tools already available. Set up missing tools with the platform's package manager or the project's model command within the current permissions. If account authorization or interactive login is required, identify the step that needs the user.

## macOS

With Homebrew, install any missing tools. FFmpeg includes ffprobe. The whisper.cpp formula includes whisper-cli.

```bash
brew install uv ffmpeg whisper.cpp
```

An existing whisper-cli configured through `CREATOR_STUDY_WHISPER` or the project cache can be reused. [Homebrew whisper.cpp formula](https://formulae.brew.sh/formula/whisper-cpp)

## Windows

Install the missing tools in PowerShell.

```powershell
winget install --id astral-sh.uv -e
winget install --id Gyan.FFmpeg -e
```

Extract the Windows CPU build of whisper.cpp for your architecture, leaving its DLLs next to the executable. Add the directory to `PATH`, or set `$env:CREATOR_STUDY_WHISPER = 'C:\Tools\whisper-cpp\whisper-cli.exe'` in PowerShell before running the CLI. Refresh the terminal's `PATH` if it does not see newly installed commands. [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases)

## Linux

Use your distribution's FFmpeg package and install uv through the package manager or the official installer. If you need to build whisper-cli, use a tools directory and point `CREATOR_STUDY_WHISPER` to the resulting executable. Example for Ubuntu or Debian:

```bash
sudo apt install ffmpeg git cmake build-essential
git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git ./whisper-cpp
cmake -S ./whisper-cpp -B ./whisper-cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build ./whisper-cpp/build -j --target whisper-cli
export CREATOR_STUDY_WHISPER="$PWD/whisper-cpp/build/bin/whisper-cli"
```

[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) · [whisper.cpp build instructions](https://github.com/ggml-org/whisper.cpp#quick-start)

## Speech model and browser

Run the commands from the user's workspace and replace `<skill>` with the absolute path to the installed Skill.

- For local transcription, run `uv run --locked --project "<skill>/runtime" creator-analyzer setup-model`. It verifies and reuses an existing model, downloading about 181 MiB when needed. You can also pass an existing compatible model to `prepare` with `--model`.
- For handle or profile collection, install Chromium if needed with `uv run --locked --project "<skill>/runtime" --extra douyin playwright install chromium`. On Linux, use `--with-deps` if browser system libraries are missing. If Douyin prompts for login, use `uv run --locked --project "<skill>/runtime" --extra douyin creator-analyzer browser-login` in a desktop session so the user can sign in.

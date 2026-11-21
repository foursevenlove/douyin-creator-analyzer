# 首次运行设置

GitHub 安装会复制 Skill 目录中的 Python 工具、报告模板和锁定的依赖清单。首次调用时，`uv run --locked` 自动准备 Python 环境。根据这次的输入补齐系统工具即可。直接渲染已准备的证据时，只需要 Python 环境。处理视频需要 FFmpeg 和 ffprobe。有可用的字幕或转写时可直接导入，需要现场转写时再配置 whisper-cli 和本地模型。

首次运行先复用机器上已有的工具。发现缺项时，使用当前平台已有的包管理器或项目提供的模型安装命令，在当前权限下完成配置。需要用户权限或交互登录时，请说明具体缺项。

## macOS

有 Homebrew 时，可以安装缺少的工具。FFmpeg 提供 ffprobe，whisper.cpp 提供 whisper-cli。

```bash
brew install uv ffmpeg whisper.cpp
```

已有通过 `CREATOR_STUDY_WHISPER` 或工具缓存配置的 whisper-cli 可以继续用。[Homebrew whisper.cpp 公式](https://formulae.brew.sh/formula/whisper-cpp)

## Windows

在 PowerShell 中安装缺少的工具。

```powershell
winget install --id astral-sh.uv -e
winget install --id Gyan.FFmpeg -e
```

选用适合本机架构的 Windows CPU 版 whisper.cpp，将可执行文件和同目录 DLL 一起解压。将目录加入用户的 `PATH`，或在运行 CLI 的 PowerShell 中设置 `$env:CREATOR_STUDY_WHISPER = 'C:\Tools\whisper-cpp\whisper-cli.exe'`。新安装的命令若未被当前进程发现，先刷新 `PATH`。[whisper.cpp 发布页](https://github.com/ggml-org/whisper.cpp/releases)

## Linux

按发行版安装 FFmpeg。uv 可以通过系统包管理器或官方安装器安装。需要从源码构建 whisper-cli 时，可在用户指定的工具目录构建，再通过 `CREATOR_STUDY_WHISPER` 指向生成的程序。以下是 Ubuntu 或 Debian 的例子。

```bash
sudo apt install ffmpeg git cmake build-essential
git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git ./whisper-cpp
cmake -S ./whisper-cpp -B ./whisper-cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build ./whisper-cpp/build -j --target whisper-cli
export CREATOR_STUDY_WHISPER="$PWD/whisper-cpp/build/bin/whisper-cli"
```

[uv 安装说明](https://docs.astral.sh/uv/getting-started/installation/) · [whisper.cpp 构建说明](https://github.com/ggml-org/whisper.cpp#quick-start)

## 模型和浏览器

在用户的工作目录运行这些命令，将 `<skill>` 替换为已安装 Skill 的绝对路径。

- 需要本地转写时，运行 `uv run --locked --project "<skill>/runtime" creator-study setup-model`。它会校验并复用已有的默认模型，必要时下载约 181 MiB 的模型。已有兼容模型也可以在 `prepare` 时用 `--model` 指定。
- 用抖音号或主页采集且缺少 Chromium 时，运行 `uv run --locked --project "<skill>/runtime" --extra douyin playwright install chromium`。Linux 缺少浏览器系统库时可加 `--with-deps`。如抖音页面要求登录，在有桌面窗口的环境运行 `uv run --locked --project "<skill>/runtime" --extra douyin creator-study browser-login`，由用户完成登录。

# Douyin Creator Analyzer · 抖音创作者分析

[English](README.md) | 简体中文

输入**抖音号、主页链接或一组视频**，研究这位博主怎么做内容。报告先给账号全貌和内容分类，再深拆代表作，最后用更广的样本说明哪些创作做法值得学习。

![第四种黑猩猩的报告预览，展示时长、互动和内容分析](docs/chaolab-report-preview.jpg)

示例使用 **@chaolab（第四种黑猩猩）** 2026 年 7 月 28 日的 171 条历史视频记录。报告对全部视频归类，按原片顺序逐条拆解点赞最高的 5 条作品，再从 20 条高赞样本总结选题、文案和画面。[查看单片拆解预览](docs/chaolab-video-preview.jpg) · [抖音主页](https://www.douyin.com/user/MS4wLjABAAAAZwr8jX4xwZqPkdc-cJ2MVWvwh3d_rHxluq1ArMrcsBjZ32WONVrcLkvpNN7-Od99)

- **整体分析**包含内容分类、发布节奏、时长分布，以及单条互动的平均数、中位数和最大值。作品清单支持搜索、排序和筛选拆解样本。
- **代表作拆解**引用开头原话，按时间拆开正文，解释文案亮点和相关画面的作用。
- **经验与证据**分别提炼选题、文案和画面的关键点，逐点解释原理，附具体作品和时间戳。
- **报告文件**包括可离线打开的 HTML、方便摘录的 Markdown 和可复核的证据清单。

## 在你的 Agent 中安装

项目采用 [Agent Skills 开放标准](https://agentskills.io/specification)。不同客户端共用一份 Skill，安装时会一起带上 Python CLI、报告模板和依赖锁文件。

请使用支持 Agent Skills 的客户端版本。在准备使用 Skill 的工作目录运行 [Skills CLI](https://github.com/vercel-labs/skills) 并选择客户端。安装器需要 Node.js 22.20 或更新版本。

```bash
npx skills add foursevenlove/douyin-creator-analyzer --skill douyin-creator-analyzer
```

也可以直接指定客户端。下面以 Claude Code 为例，默认安装到当前项目。希望在所有项目里使用时，加上 `--global`。

```bash
npx --yes skills add foursevenlove/douyin-creator-analyzer --skill douyin-creator-analyzer --agent claude-code --yes
```

| 客户端 | 安装参数 | 官方文档 |
| --- | --- | --- |
| Claude Code | `claude-code` | [Claude Code Skills](https://code.claude.com/docs/en/skills) |
| Cursor | `cursor` | [Cursor Agent Skills](https://cursor.com/docs/skills) |
| Gemini CLI | `gemini-cli` | [Gemini CLI Agent Skills](https://geminicli.com/docs/cli/skills/) |
| GitHub Copilot（CLI 或 VS Code） | `github-copilot` | [GitHub Copilot Agent Skills](https://docs.github.com/en/copilot/concepts/customizations/agent-skills) |
| OpenCode | `opencode` | [OpenCode Skills](https://opencode.ai/docs/skills/) |
| OpenClaw | `openclaw` | [OpenClaw Skills](https://docs.openclaw.ai/tools/skills) |
| Codex | `codex` | [Codex Agent Skills](https://developers.openai.com/codex/skills/) |

使用表外其他支持 Agent Skills 的客户端时，可以把整个 [Skill 目录](.agents/skills/douyin-creator-analyzer/)复制到它读取的目录，保留 `SKILL.md`、`runtime/` 和 `references/`。支持直接发现 `.agents/skills/` 的客户端也可以打开本仓库使用。

<details>
<summary>在 Codex 对话里直接安装</summary>

```text
请用 $skill-installer 安装 https://github.com/foursevenlove/douyin-creator-analyzer/tree/main/.agents/skills/douyin-creator-analyzer
```

</details>

## 使用 Skill

在工作目录开启一个新的 Agent 会话，直接点名使用 Skill。

> 用 douyin-creator-analyzer 分析抖音号 chaolab。先看作品数据与内容分布，深拆 5 条代表作，再用更广的样本总结选题、文案和画面风格。

Claude Code 和 Cursor 也可以用 `/douyin-creator-analyzer`，Codex 可以用 `$douyin-creator-analyzer`。

Agent 需要能够运行终端命令和访问工作区文件。能读取图片时可做画面分析。首次调用会由 uv 准备 Python 依赖，再按输入类型补齐 FFmpeg 等工具。[macOS](.agents/skills/douyin-creator-analyzer/references/setup.md#macos) · [Windows](.agents/skills/douyin-creator-analyzer/references/setup.md#windows) · [Linux](.agents/skills/douyin-creator-analyzer/references/setup.md#linux) · [模型与浏览器](.agents/skills/douyin-creator-analyzer/references/setup.md#speech-model-and-browser)

Whisper 在本机转写，FFmpeg 在本机抽帧和测量音轨。Agent 用当前会话分析文字、画面和数值，无需为 Skill 另配分析或转写 API Key。命令行提示使用英文，报告模板界面使用中文。

## 从源码运行

也可以直接使用命令行。在仓库根目录安装 Python 依赖。按[首次运行设置](.agents/skills/douyin-creator-analyzer/references/setup.md)配置系统工具，下面的后两步对应需要转写和浏览器采集的场景。

```bash
uv sync --locked --extra douyin
uv run --locked creator-analyzer setup-model
uv run --locked --extra douyin playwright install chromium
```

只处理本地视频时，Python 环境可用 `uv sync --locked` 安装。构建 Python 分发包时，运行 `uv build --package douyin-creator-analyzer`。

## 采集来源与命令行

| 已有输入 | 适用方式 |
| --- | --- |
| 抖音号或主页链接 | 启动项目专用 Chromium，读取可访问的作品列表，选样并下载 |
| 作品链接清单 | 逐条下载，每行一个 `https://www.douyin.com/video/<id>` |
| 本地视频目录 | 直接抽帧和转写 |
| 作品快照 JSON | 用快照生成数据总览，结合链接或本地视频深读 |

```bash
uv run --extra douyin creator-analyzer prepare chaolab --out runs/chaolab
uv run --extra douyin creator-analyzer prepare --links links.txt --out runs/links
uv run creator-analyzer prepare --videos ./videos --out runs/local
uv run creator-analyzer prepare --snapshot snapshot.json --videos ./videos --strategy top --out runs/snapshot
uv run creator-analyzer render --out runs/local
```

`prepare` 整理证据并保存进度。独立使用 CLI 时，先按[分析格式](.agents/skills/douyin-creator-analyzer/references/analysis.md)写好 `analysis.json`，再运行 `render`。同一来源和取样配置可以用相同的 `--out` 续跑。更换来源或样本数量时使用新目录。

- 网页采集受抖音登录、验证和作品可见范围影响。运行 `uv run --extra douyin creator-analyzer browser-login` 打开项目专用窗口，登录确认后窗口会自动关闭。提供主页链接时可配合 `--expect-handle <抖音号>` 核验账号。
- Agent 可以用公开索引核对抖音号、主页和可下载作品，生成标明来源的索引样本报告。需要较完整的作品数据时，使用可访问的主页列表或已有快照。
- 下载优先使用 yt-dlp，公开作品下载失败时会尝试[固定版本的备用下载器](https://github.com/yt-dlp/yt-dlp/pull/17826)。可用 `--downloader yt-dlp` 指定只用标准版，也可传入兼容可执行文件。手头已有经授权的 Netscape cookies 文件时，可通过 `--cookies` 指定。
- 单次默认深读 12 条。同期作品数量和点赞覆盖足够时按近 90 天点赞分层，否则按已知日期或来源顺序。历史高赞使用 `--strategy top`。网页收集上限为 `min(80, 4 × 样本数)`，实际条数取决于访问结果。

<details>
<summary>快照和转写格式</summary>

快照是包含 `posts` 数组的 JSON。每条支持 `id`、`title`、`url`、`published_at`、`duration`、`likes`、`comments`、`favorites`、`shares`、`views`、`media` 和 `transcript`，也兼容旧快照里的 `aweme_id`、`desc`、`create_time`、`duration_ms` 和 `statistics`。

本地文件名可用作品 ID 或 `01-<作品ID>.mp4` 与快照关联。`media` 和 `transcript` 支持相对快照的路径。导入的转写采用秒为单位，例如 `[{"start": 0.6, "end": 3.4, "text": "口播内容"}]`。

</details>

## 输出文件

| 路径 | 内容 |
| --- | --- |
| `report.html` | 离线报告，含作品清单、关键帧、声音数据和试听 |
| `report.md` | 分析正文和证据链接 |
| `manifest.json` | 作品来源、取样方式、证据覆盖和失败记录 |
| `evidence/` | 关键帧、转写文件和试听片段 |

移动 HTML 时，将它与 `evidence/` 一并保留。互动指标以来源记录为准，缺失在报告中显示为「—」。当作品已有互动而播放数字为零时，报告将播放量视为缺失。

快照加本地视频、公开索引加在线下载两条流程都在 macOS Apple Silicon 实测至报告生成。Windows 和 Linux 提供了安装步骤，运行前可用 `ffmpeg -version`、`ffprobe -version` 和 `whisper-cli --help` 或指定的 Whisper 程序检查依赖。

## 许可证

项目代码遵循 [MIT](LICENSE)。报告截图中的作品画面属于原作者，浏览器会话与研究素材保存在本机。

# Douyin Creator Analyzer

English | [简体中文](README.zh-CN.md)

Analyze a Douyin creator from a handle, profile link, or set of videos. Get an account overview, examine representative videos one at a time, and learn how the creator chooses topics, structures scripts, and uses visuals.

![Sample report for @chaolab with video durations, engagement metrics, and content categories](docs/chaolab-report-preview.jpg)

The sample report uses a July 28, 2026 snapshot of 171 videos from **@chaolab (第四种黑猩猩)**. It classifies the full catalog, breaks down the five most-liked videos in playback order, and draws on 20 high-engagement videos to explain recurring techniques. [Preview a video breakdown](docs/chaolab-video-preview.jpg) · [Douyin profile](https://www.douyin.com/user/MS4wLjABAAAAZwr8jX4xwZqPkdc-cJ2MVWvwh3d_rHxluq1ArMrcsBjZ32WONVrcLkvpNN7-Od99)

- **Account overview** shows topic categories, posting activity, duration distribution, and mean, median, and maximum engagement. The video catalog is searchable and sortable.
- **Video breakdowns** quote each opening, follow the script through its transitions, and explain the role of specific lines and frames.
- **Creator lessons** organize takeaways by topic choice, writing, and visuals. Each principle includes examples and timestamps.
- **Reports** are exported as offline HTML and Markdown, with an evidence manifest for verification. The bundled report interface uses Chinese labels.

## Install in your agent

This project follows the [Agent Skills standard](https://agentskills.io/specification). The same Skill bundles the Python CLI, report templates, and dependency lockfile for each supported client.

Use a client version that supports Agent Skills. From the workspace where you want to use it, run the [Skills CLI](https://github.com/vercel-labs/skills) with Node.js 22.20 or later and select your agent.

```bash
npx skills add foursevenlove/douyin-creator-analyzer --skill douyin-creator-analyzer
```

For non-interactive installation, pass your agent's ID. This example installs into the current project for Claude Code. Add `--global` if you want the Skill in all your projects.

```bash
npx --yes skills add foursevenlove/douyin-creator-analyzer --skill douyin-creator-analyzer --agent claude-code --yes
```

| Agent | Installer ID | Skill documentation |
| --- | --- | --- |
| Claude Code | `claude-code` | [Claude Code Skills](https://code.claude.com/docs/en/skills) |
| Cursor | `cursor` | [Cursor Agent Skills](https://cursor.com/docs/skills) |
| Gemini CLI | `gemini-cli` | [Gemini CLI Agent Skills](https://geminicli.com/docs/cli/skills/) |
| GitHub Copilot (CLI or VS Code) | `github-copilot` | [GitHub Copilot Agent Skills](https://docs.github.com/en/copilot/concepts/customizations/agent-skills) |
| OpenCode | `opencode` | [OpenCode Skills](https://opencode.ai/docs/skills/) |
| OpenClaw | `openclaw` | [OpenClaw Skills](https://docs.openclaw.ai/tools/skills) |
| Codex | `codex` | [Codex Agent Skills](https://developers.openai.com/codex/skills/) |

If your agent supports Agent Skills but is not listed, copy the entire [Skill directory](.agents/skills/douyin-creator-analyzer/) to the workspace or user-level Skills directory it reads. Keep `SKILL.md`, `runtime/`, and `references/` together. Clients that discover `.agents/skills/` can also load it when you open this repository.

<details>
<summary>Install directly from a Codex chat</summary>

```text
Use $skill-installer to install https://github.com/foursevenlove/douyin-creator-analyzer/tree/main/.agents/skills/douyin-creator-analyzer
```

</details>

## Use the Skill

Start a new agent session in the workspace and ask for the Skill by name.

> Use douyin-creator-analyzer to analyze @chaolab. Summarize its posting and engagement data, break down five representative videos, and explain what creators can learn from its topics, scripting, and visuals.

Claude Code and Cursor also accept `/douyin-creator-analyzer`. In Codex, use `$douyin-creator-analyzer`.

The agent needs access to a shell and local workspace files. Image viewing enables visual analysis. Python dependencies are provisioned via uv on first use. Set up FFmpeg and the remaining tools as needed for your input. [macOS](.agents/skills/douyin-creator-analyzer/references/setup.md#macos) · [Windows](.agents/skills/douyin-creator-analyzer/references/setup.md#windows) · [Linux](.agents/skills/douyin-creator-analyzer/references/setup.md#linux) · [Speech model and browser](.agents/skills/douyin-creator-analyzer/references/setup.md#speech-model-and-browser)

Whisper transcribes speech locally, and FFmpeg extracts frames and measures the soundtrack. Your agent analyzes transcript text, images, and measurements using its existing session. The Skill requires no separate analysis or transcription API key.

## Run from source

To run without an agent, [set up system tools](.agents/skills/douyin-creator-analyzer/references/setup.md) and run these commands from the repository root.

```bash
uv sync --locked --extra douyin
uv run --locked creator-analyzer setup-model
uv run --locked --extra douyin playwright install chromium
```

Use the `douyin` extra for online retrieval and the Chromium install for profile collection. For local files, `uv sync --locked` is enough to install the Python dependencies. Run `setup-model` when local transcription is needed. Build the Python distribution with `uv build --package douyin-creator-analyzer`.

## Inputs and CLI

| Input | Workflow |
| --- | --- |
| Douyin handle or profile URL | List accessible posts with a dedicated Chromium profile, select a sample, and download it |
| Post URL list | Download posts from a text file with one canonical Douyin video URL per line |
| Local video directory | Extract frames and transcribe speech locally |
| JSON snapshot | Compute catalog statistics and analyze posts using linked or local videos |

```bash
uv run --extra douyin creator-analyzer prepare chaolab --out runs/chaolab
uv run --extra douyin creator-analyzer prepare --links links.txt --out runs/links
uv run creator-analyzer prepare --videos ./videos --out runs/local
uv run creator-analyzer prepare --snapshot snapshot.json --videos ./videos --strategy top --out runs/snapshot
uv run creator-analyzer render --out runs/local
```

`prepare` saves its evidence and progress. Standalone CLI users write `analysis.json` using the [analysis schema](.agents/skills/douyin-creator-analyzer/references/analysis.md) before running `render`. Reuse the same `--out` directory to resume with the same source and sampling options. Use a new directory when these options change.

- Profile collection depends on what Douyin makes available. Run `uv run --extra douyin creator-analyzer browser-login` to sign in through the dedicated window. It closes after login is detected. Use `--expect-handle` with a direct profile URL to verify the handle.
- Your agent can use publicly indexed posts if a profile list is unavailable. For a more complete catalog, supply an accessible profile or a snapshot export.
- Downloads use yt-dlp, with a [pinned fallback build](https://github.com/yt-dlp/yt-dlp/pull/17826) for public posts when needed. Use `--downloader yt-dlp` to select the standard downloader or `--cookies` with an authorized Netscape cookies file.
- The default sample is 12 posts. With sufficient recent dates and likes, the sampler selects across engagement tiers from the last 90 days. Otherwise it uses the available chronology or source order. Use `--strategy top` to rank by recorded likes. Profile collection reads up to `min(80, 4 × sample size)` accessible posts.

<details>
<summary>Snapshot and transcript formats</summary>

A snapshot is a JSON object with a `posts` array. Each post can include `id`, `title`, `url`, `published_at`, `duration`, `likes`, `comments`, `favorites`, `shares`, `views`, `media`, and `transcript`. Older snapshots using `aweme_id`, `desc`, `create_time`, `duration_ms`, and `statistics` also work.

Local filenames can match a snapshot by post ID or use `01-<post-id>.mp4`. The `media` and `transcript` paths can be relative to the snapshot. Imported transcript times are in seconds, as in `[{"start": 0.6, "end": 3.4, "text": "Spoken text"}]`.

</details>

## Outputs

| Path | Contents |
| --- | --- |
| `report.html` | Offline report with a post catalog, keyframes, soundtrack measurements, and local audio previews |
| `report.md` | Text analysis with links to evidence |
| `manifest.json` | Sources, sampling, evidence coverage, and processing errors |
| `evidence/` | Keyframes, timestamped transcripts, and listening clips |

Keep `evidence/` alongside the HTML when moving a report. Missing metrics display as a dash. A zero view count on a post with recorded engagement is treated as missing.

GitHub installation and local video analysis through report export were tested on macOS Apple Silicon. The platform setup guide also covers Windows and Linux.

## License

Project code is released under the [MIT License](LICENSE). The video frames in the sample reports belong to their original creators. Browser sessions and research material are stored locally.

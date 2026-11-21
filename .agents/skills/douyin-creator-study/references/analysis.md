# analysis.json

Use `schema_version: 1`. Every `evidence` entry points to an inspected item such as `作品ID/f01` for a frame, `作品ID/t0001` for a transcript segment or `作品ID/audio-metrics` for local soundtrack measurements. The frame IDs and measurement fields are in `manifest.json`. Transcript segments with IDs, seconds and text are in each post's transcript file. The sample below shows structure only. Replace its references with evidence from the current run.

```json
{
  "schema_version": 1,
  "title": "博主研究报告",
  "summary": "概括这份报告针对原作精读的几个问题。",
  "studies": [
    {
      "title": "为什么开场先给观众看成品界面？",
      "observed": "用几个有时间定位的原作片段还原顺序。可用空行分段。",
      "analysis": "解释这些选择怎样起作用，必要时用另一处原作来对照。",
      "lesson": "说明读者通过这一段能理解什么，以及证据支持到哪里。",
      "evidence": ["local-001/f01", "local-001/t0001"]
    }
  ],
  "videos": [
    {
      "post_id": "local-001",
      "topic": "帮观众解决的具体问题",
      "observation": "视频主题、脚本顺序与交付结果。有缺项就说明。",
      "script": "标题、开头承诺和段落推进。",
      "visual": "画面如何支撑口播或演示。",
      "voice": "依据时间戳、转写措辞与本地混音指标描述。",
      "evidence": ["local-001/f01", "local-001/t0001"]
    }
  ],
  "findings": [
    {
      "category": "visuals",
      "title": "可复用的做法",
      "detail": "有哪些作品支持，机制只作为解释或假设。",
      "evidence": ["local-001/f01"],
      "counter_evidence": []
    }
  ],
  "ideas": [
    {
      "title": "一个可拍的原创选题",
      "audience": "受众及其具体问题",
      "angle": "用创作者自己的案例或素材完成什么",
      "opener": "前几秒可以实拍的画面和承诺",
      "test": "如何用自己的发布数据或试看片验证",
      "evidence": ["local-001/t0001"]
    }
  ],
  "limitations": "样本选择、缺失项和结论适用范围。"
}
```

Categories for findings and takeaways are `topics`, `script`, `style`, `visuals`, `audio`, `duration`, `workflow`, `review` and `other`. Evidence is required for each study, takeaway, video, finding and idea. `counter_evidence` is an optional array for findings. `script`, `visual` and `voice` are optional video fields. Include every analyzable video in `videos`. A partial source may support a partial observation.

Learning reports use `studies`. Adaptation requests can use `takeaways`, with `category`, `title`, `observed`, `how`, `example`, `check` and `evidence` in each item. Provide `ideas` when standalone topics are requested. The renderer accepts at least one item across these three arrays and supports up to three ideas.

## Full account report

Use an `editorial` object with these fields. The renderer builds the data charts from the manifest.

- `taxonomy` contains `title`, `detail` and `post_ids` for each group. Assign each catalog video to exactly one group.
- `style` summarizes the content and its observed visual style. Name the coverage for each claim.
- `selection` states the case selection criteria. Keep only those deep cases in `videos`. Use `observation` as the case lead. Keep the required `topic`, `script`, `visual` and `evidence` fields, then add `script_breakdown` to render a single-video close reading.
- `readings` contains one item per evidence-ready sample, with `post_id`, `opening`, `visual`, `note` and same-video `evidence`. Use consistent opening and visual labels to make the counts meaningful.
- `synthesis` contains a module for topic, writing and visuals. Give each module `title`, `points` and `summary`. Each point has a short `title`, a `principle` explaining why it works, a concrete `example`, and `evidence`. The renderer uses the point titles to build the numbered overview and expands the same points in order. `summary` recaps the module. Older entries using the `studies` fields still render.
- `conclusion` gives the main takeaway. `sources` states date, coverage, classification and sampling method. Use top-level `limitations` for the interpretation limits.

### Single-video script breakdown

`videos[].script_breakdown` has four fields:

- `opening` contains `quote`, `analysis` and `evidence` with the original transcript segment IDs. The renderer derives the quote's time range.
- `throughline` connects the opening promise, the body and the payoff in one sentence.
- `beats` lists the sections in chronological order. Each uses `at` for the bare starting transcript segment ID, such as `t0011`, `title` for the section's job, `detail` for what is said and how it contributes, and `evidence`. The renderer displays the interval up to the next section or the end of the video. Include an evidence frame when it materially explains that section. Use `frame_note` to point out a visible detail in its caption.
- `highlights` lists specific notable lines. Each has `title`, `quote`, `analysis` and transcript `evidence`. Explain what the line sets up, why it connects with this audience, or what keeps the question open.

### Optional paired pages

For explicitly requested comparisons, add `editorial.comparisons`. Each page uses `title`, `difference`, `visual_heading`, `action` and two `works`. Each work has a catalog `post_id`, an `angle`, an `opening` with `quote`, transcript `evidence`, `frame_id` and `note`, and a `visual` with `frame_id` and `note`. The renderer reads dates and likes from the catalog. It derives quote ranges and frame times from evidence. Include a specific area of the image to inspect in the note.

For extra works or exact-time stills, put the new assets under `evidence/<post_id>/` and add their records to `comparison-evidence.json` alongside the report. This file is an object with a `posts` array. Each post has `id`, `title`, optional `transcript`, and `frames` using the manifest format. Extra evidence IDs must be distinct from existing ones for that work.

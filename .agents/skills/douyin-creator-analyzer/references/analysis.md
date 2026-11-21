# analysis.json

Use `schema_version: 1`. Every `evidence` entry points to an inspected item such as `post-id/f01` for a frame, `post-id/t0001` for a transcript segment or `post-id/audio-metrics` for local soundtrack measurements. The frame IDs and measurement fields are in `manifest.json`. Transcript segments with IDs, seconds and text are in each post's transcript file. The sample below shows structure only. Replace its references with evidence from the current run.

```json
{
  "schema_version": 1,
  "title": "Creator analysis report",
  "summary": "Summarize the questions this report answers.",
  "studies": [
    {
      "title": "Why show the finished interface in the opening?",
      "observed": "Reconstruct the sequence using timestamped passages. Separate paragraphs with blank lines.",
      "analysis": "Explain how these choices work, with another passage for comparison if helpful.",
      "lesson": "Explain what a creator can learn and what the evidence supports.",
      "evidence": ["local-001/f01", "local-001/t0001"]
    }
  ],
  "videos": [
    {
      "post_id": "local-001",
      "topic": "The specific problem the video addresses",
      "observation": "Describe the subject, script sequence, and result. Note any gaps in the evidence.",
      "script": "Describe the title, opening promise, and progression.",
      "visual": "Explain how the visuals support the narration or demonstration.",
      "voice": "Use timestamps, transcript wording, and measured soundtrack properties.",
      "evidence": ["local-001/f01", "local-001/t0001"]
    }
  ],
  "findings": [
    {
      "category": "visuals",
      "title": "A technique worth studying",
      "detail": "Name the supporting videos and explain how the technique may work.",
      "evidence": ["local-001/f01"],
      "counter_evidence": []
    }
  ],
  "ideas": [
    {
      "title": "An original topic for a video",
      "audience": "The audience and its specific problem",
      "angle": "What the creator can demonstrate with their own material",
      "opener": "A filmable moment and a promise for the opening seconds",
      "test": "How to test the idea with publishing data or a screening",
      "evidence": ["local-001/t0001"]
    }
  ],
  "limitations": "Sampling, missing evidence, and scope of the conclusions."
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

# Full account report workflow

Use this workflow with the [analysis schema](analysis.md). The agent writes the analysis from the prepared sources, then runs `creator-study render --out <run>` to export HTML and Markdown.

## Overall data and content

Use the manifest inventory to report coverage. Show the per-video average, median and maximum for each available interaction metric. The renderer computes them from the same set of recorded values. Classify each catalog video by the principal question or promise in its publishing text. Give the snapshot date and separate what title classification can support from observations made by viewing frames.

## Representative videos

Choose a few representative high-performing works, usually three to five if the material allows. Write one `script_breakdown` per chosen video. Read the available transcript from beginning to end before writing about its structure. Check relevant frames or subtitles when transcription makes a name or phrase unclear.

1. **Opening.** Quote what the creator actually says and cite the transcript range. Identify what the audience knows after the first few sentences, what question or objection the opener responds to, and what it sets up for the rest of this particular video.
2. **Main body.** Identify transitions in what the creator is doing, such as changing from defining the problem to introducing a comparison or from showing a demo to checking the result. Record each section's first transcript segment, what the section says, and how it advances the previous section or the title's promise. Connect the sections into one sentence that includes the payoff. Put keyframes beside the section they explain and caption the specific detail to look at.
3. **Script highlights.** Select the specific lines that carry the most weight. Explain the audience concern, surprise, tension, or unanswered question the line speaks to and where the video picks it up again. Use observable wording and placement. Describe the possible effect on attention as an interpretation unless retention data is available.

Look for the distinction between a phrase and its job. For example, a line promising “we'll compare the three plans” commits the creator to an answer. If the next section introduces three criteria and the conclusion applies those criteria, explain that connection with the actual lines and timestamps. A chapter list that could describe many unrelated videos is a cue to revisit the transitions.

## Learning modules

Review a wider set of usable works across the relevant formats. Record each sample's opening, dominant visual form and sources in `editorial.readings`. Name the actual coverage and the bias from selection by engagement or media availability.

Write separate modules for topic choice, writing and visuals in `editorial.synthesis`. Use the same order inside each module:

1. Start with a short numbered list of the most memorable points. Use action or mechanism phrasing, usually around three points that the evidence supports.
2. Expand each point in that order. Explain the principle and why it matters, then show where it appears in a specific work with evidence. Where the same technique behaves differently across formats, name the condition that changes its use.
3. End with a brief recap that explains how the points work together.

Use each numbered point for one idea. An opening that promises an outcome and one that starts with a surprising event can both work because they resolve different audience questions. Explain which audience question each answers, and show the actual setup and follow-through before generalizing.

## Before delivery

1. Recompute the interaction summary from the inventory and check average, median, maximum and coverage in the output. Check that the category counts reconcile to the video count.
2. Read each rendered case alongside its complete transcript. Check the opening and each quoted line against the cited text. Read around each section boundary and verify what changes there, how the section serves the overall logic, and what the ending actually delivers. Inspect each cited frame for the detail the reader is asked to notice. Keep uncertainty about intent, retention, and product outcomes tied to the available evidence.
3. Read each learning module from its numbered opening through its recap. Each explanation should show what the principle does in the cited work, and the examples across the modules should extend beyond the deep cases when the material supports it. Rewrite any point that could be copied onto unrelated videos without changing its explanation.
4. Open the generated HTML on desktop and mobile, and check screenshots, navigation and local evidence links. Review the Markdown for the same case order, conclusions and evidence. Correct issues in `analysis.json` and rerender before delivering the files. When the user asks to regenerate an existing report, verify the actual run outputs. For an update limited to the Skill, a temporary run is sufficient.

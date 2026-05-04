---
name: manim-video
description: "Creates 3Blue1Brown-style animated explainer videos with Manim Community Edition. Use when asked for Manim animations, 3Blue1Brown-style explainers, equation derivations, algorithm visualizations, architecture animations, or programmatic technical videos."
---

# Manim Video

Build mathematical and technical animations with Manim Community Edition.

## When To Use

Use this skill when the user asks for:
- 3Blue1Brown-style videos
- Manim scenes or animations
- animated math or geometry explainers
- equation derivations
- algorithm walkthroughs
- architecture or systems build-up animations
- narrated technical explainer videos

## First Principles

- Start with the teaching goal, not the code. Identify the misconception, the key reveal, and the visual sequence that makes the idea click.
- Show geometry before algebra when possible. Make the viewer see the structure before reading the formula.
- Keep one coherent visual language per video: background, palette, type scale, and animation tempo should feel like one system.
- Give each reveal breathing room. After every major animation, pause long enough for a human to absorb it.
- Prefer a small number of clear, purposeful elements over dense slide-like scenes.

## Environment Check

When the user asks for a rendered artifact, start with:

```bash
bash .agents/skills/manim-video/scripts/setup.sh
```

The setup script verifies `uv`, `ffmpeg`, and LaTeX, and it auto-installs `manim`
with `uv tool install` if the CLI is missing.

Do not fall back to script-only output for an explicit video request until you have:
- run `setup.sh`
- let the `uv` bootstrap path try to install `manim`
- attempted at least one draft render after setup succeeds

If setup still fails because native system packages are missing, explain that the
render path is blocked and still produce `plan.md` and `script.py`.

## Workflow

### 1. Plan First

Before writing code, create a short plan that includes:
- the audience and teaching goal
- the "aha" moment
- 3 to 7 scenes with one sentence each
- the visual metaphor for each scene
- the palette and typography choices
- optional narration or subtitle lines

Use this template:

```markdown
# Video Plan

## Goal
- Explain:
- Audience:
- Aha moment:

## Style
- Background:
- Primary color:
- Secondary color:
- Accent color:
- Font:

## Scenes
1. Title / hook
2. Setup
3. Core mechanism
4. Key reveal
5. Takeaway
```

### 2. Write One Script File

Use one `script.py` file with one Manim scene class per scene. Keep scenes independently renderable.

Project shape:

```text
project-name/
  plan.md
  script.py
  concat.txt
  final.mp4
  media/
```

### 3. Use A Consistent Base Style

Define shared constants once near the top of `script.py`:

```python
from manim import *

BG = "#1C1C1C"
PRIMARY = "#58C4DD"
SECONDARY = "#83C167"
ACCENT = "#FFFF00"
MONO = "Menlo"
```

Good default palette:
- background: `#1C1C1C`
- primary: `#58C4DD`
- secondary: `#83C167`
- accent: `#FFFF00`

Typography defaults:
- title: `48`
- section heading: `36`
- body: `30`
- label: `24`
- caption: `20`

Prefer a monospace text font in Manim because proportional fonts often kern poorly through Pango.

### 4. Scene Pattern

Use this baseline scene pattern unless the task needs something more specialized:

```python
class Scene1_Intro(Scene):
    def construct(self):
        self.camera.background_color = BG

        title = Text(
            "Why This Works",
            font=MONO,
            font_size=48,
            color=PRIMARY,
            weight=BOLD,
        )

        self.add_subcaption("Why this works", duration=2)
        self.play(Write(title), run_time=1.5)
        self.wait(1.0)
        self.play(FadeOut(title), run_time=0.5)
```

### 5. Render Drafts First

For explicit video requests, attempt a real draft render before claiming the environment is good:

```bash
manim -ql script.py Scene1_Intro Scene2_CoreConcept
```

Use `-qm` for text-heavy previews when 480p hides layout problems.

### 6. Render The Final Artifact

Once the draft is structurally correct, render the final scene set at higher quality:

```bash
manim -qh script.py Scene1_Intro Scene2_CoreConcept
```

If multiple scene clips are produced, stitch them with `ffmpeg`:

```text
file 'media/videos/script/1080p60/Scene1_Intro.mp4'
file 'media/videos/script/1080p60/Scene2_CoreConcept.mp4'
```

```bash
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy final.mp4
```

### 7. Fallback Only After Exhausting The Render Path

For an explicit render request, script-only output is acceptable only after the setup script and at least one draft render attempt leave the environment blocked.

## Implementation Rules

- Use raw strings for LaTeX: `MathTex(r"\\frac{1}{2}")`
- Set `self.camera.background_color` in every scene
- Fade out or transform old elements before layering new text on top of them
- Keep labels away from the edge: use `buff >= 0.5` for `to_edge(...)`
- Use opacity to guide attention: primary content at `1.0`, supporting context around `0.4`, structural guides around `0.15`
- Avoid cramming every idea into one scene; split the explanation into separate beats
- End each scene cleanly so later scenes do not inherit stray mobjects

## Quality Bar

Reject the result and revise if any of these are true:
- the scene reads like static slides with token animations
- the important object is not visually dominant
- text is too small to read comfortably
- multiple colors are used without semantic purpose
- transitions are so fast that the main reveal is easy to miss
- the explanation is technically correct but pedagogically flat

## Default Deliverables

When the user asks for a Manim video and does not specify otherwise, aim to produce:
- `plan.md`
- `script.py`
- draft render command(s)
- final render command(s)
- `concat.txt` when there are multiple scenes
- `final.mp4` when the environment supports rendering and the user asked for a rendered artifact

Do not claim the video is finished unless you verified the actual rendered artifact the user asked for.

"""
visuals.py — Subject-aware visual generation (section 10 of the brief).

Renders each lesson segment as a 1280x720 "slide" PNG containing:
  - the segment title
  - on-screen bullet/explanation text
  - a subject-appropriate visual: an equation render, a simple graph,
    a labeled diagram, a timeline, or a code block — chosen from
    `segment["visual_type"]`.

No paid image-generation API is used; everything is drawn deterministically
with PIL + matplotlib so the app works fully offline. Swap point: replace
`render_visual()` internals with a call to an image-gen API (e.g. an
Anthropic/OpenAI image tool or Stable Diffusion) for richer illustrations —
the rest of the pipeline (slide composition, video assembly) is unaffected.
"""
import os
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (18, 22, 38)
ACCENT = (94, 173, 255)
TEXT = (235, 238, 245)
MUTED = (150, 160, 180)


def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap_draw(draw, text, xy, font, max_width, fill, line_spacing=10):
    x, y = xy
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=max_width) or [""]
        for line in wrapped:
            draw.text((x, y), line, font=font, fill=fill)
            bbox = draw.textbbox((x, y), line, font=font)
            y += (bbox[3] - bbox[1]) + line_spacing
        y += line_spacing
    return y


def _visual_panel(visual_type: str, description: str, subject: str) -> Image.Image:
    """Renders the right-hand visual panel depending on subject/visual type."""
    fig, ax = plt.subplots(figsize=(5.6, 5.2), dpi=100)
    fig.patch.set_facecolor("#0f1220")
    ax.set_facecolor("#0f1220")
    for spine in ax.spines.values():
        spine.set_color("#444")

    vt = (visual_type or "diagram").lower()

    if vt in ("graph", "chart"):
        x = np.linspace(-5, 5, 200)
        y = np.sin(x) * np.exp(-0.15 * np.abs(x))
        ax.plot(x, y, color="#5eadff", linewidth=2.5)
        ax.axhline(0, color="#555", linewidth=1)
        ax.axvline(0, color="#555", linewidth=1)
        ax.set_title("Illustrative graph", color="#eee", fontsize=12)
        ax.tick_params(colors="#999")

    elif vt == "equation":
        ax.axis("off")
        ax.text(0.5, 0.6, "f(x)", fontsize=30, color="#5eadff", ha="center")
        ax.text(0.5, 0.4, "= a·x² + b·x + c", fontsize=20, color="#eee", ha="center")
        ax.text(0.5, 0.15, description[:60], fontsize=10, color="#999", ha="center", wrap=True)

    elif vt == "timeline":
        ax.axis("off")
        n = 4
        xs = np.linspace(0.1, 0.9, n)
        ax.plot([0.05, 0.95], [0.5, 0.5], color="#5eadff", linewidth=2)
        for i, x in enumerate(xs):
            ax.scatter([x], [0.5], color="#5eadff", s=80, zorder=3)
            ax.text(x, 0.58, f"Event {i+1}", color="#eee", fontsize=10, ha="center")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    elif vt == "code":
        ax.axis("off")
        code_sample = (
            "def explain(topic):\n"
            "    plan = build_lesson(topic)\n"
            "    for step in plan:\n"
            "        teach(step)\n"
            "        check_understanding()\n"
        )
        ax.text(0.05, 0.9, code_sample, fontsize=11, color="#8be28b",
                family="monospace", va="top")

    elif vt == "process":
        ax.axis("off")
        steps = ["Input", "Process", "Output"]
        for i, s in enumerate(steps):
            cx = 0.2 + i * 0.3
            box = plt.Rectangle((cx - 0.1, 0.45), 0.2, 0.1, color="#5eadff", alpha=0.25)
            ax.add_patch(box)
            ax.text(cx, 0.5, s, color="#eee", fontsize=11, ha="center", va="center")
            if i < len(steps) - 1:
                ax.annotate("", xy=(cx + 0.2, 0.5), xytext=(cx + 0.1, 0.5),
                            arrowprops=dict(arrowstyle="->", color="#5eadff"))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    else:  # generic diagram
        ax.axis("off")
        circle = plt.Circle((0.5, 0.6), 0.2, color="#5eadff", alpha=0.3)
        ax.add_patch(circle)
        ax.text(0.5, 0.6, "Concept", color="#eee", fontsize=12, ha="center", va="center")
        ax.text(0.5, 0.2, description[:70], color="#999", fontsize=9, ha="center", wrap=True)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    fig.tight_layout(pad=1.0)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf).convert("RGB")
    plt.close(fig)
    return img


def render_slide(segment: dict, subject: str, segment_index: int, total: int, out_path: str) -> str:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # header
    draw.rectangle([0, 0, W, 70], fill=(12, 15, 28))
    draw.text((30, 20), f"AI Teacher  •  Part {segment_index}/{total}", font=_font(22, bold=True), fill=ACCENT)

    # left column: title + explanation text ("on-screen text")
    title = segment.get("title", "")
    draw.text((40, 100), title, font=_font(28, bold=True), fill=TEXT)

    y = 150
    explanation = segment.get("explanation", "")
    y = _wrap_draw(draw, explanation, (40, y), _font(18), max_width=48, fill=TEXT)

    example = segment.get("example", "")
    if example:
        draw.text((40, y + 10), "Example:", font=_font(16, bold=True), fill=ACCENT)
        y = _wrap_draw(draw, example, (40, y + 40), _font(16), max_width=50, fill=MUTED)

    # right column: subject-aware visual
    panel = _visual_panel(segment.get("visual_type"), segment.get("visual_description", ""), subject)
    panel = panel.resize((560, 520))
    canvas.paste(panel, (680, 110))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    return out_path

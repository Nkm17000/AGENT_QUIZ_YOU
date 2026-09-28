import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import ASSETS_DIR, VIDEO_HEIGHT, VIDEO_WIDTH

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F\u1CD0-\u1CFF\uA8E0-\uA8FF]")
FONT_EN = ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
FONT_EN_BOLD = ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
FONT_HI = ASSETS_DIR / "fonts" / "NotoSansDevanagari-Regular.ttf"

_LOGO = None
_BG_CACHE = {}


# Clean, subject-specific visual system.  No diagonal lines, grids, frames,
# or other patterns are used because these become distracting on mobile/YouTube.
THEMES = {
    "ENGLISH": {
        "top": (31, 18, 55), "bottom": (73, 28, 67),
        "blob1": (244, 105, 126), "blob2": (247, 180, 72),
        "accent": (255, 181, 82), "accent2": (255, 111, 145),
        "card": (43, 27, 66), "card_outline": (255, 126, 151),
        "text": (255, 255, 255), "subtext": (239, 211, 231),
        "correct": (239, 155, 75), "correct_outline": (255, 214, 130),
        "correct_text": (40, 25, 34), "correct_hi": (76, 47, 52),
        "explanation": (32, 24, 47), "explanation_outline": (255, 181, 82),
        "explanation_title": (255, 196, 104), "explanation_text": (255, 255, 255),
        "explanation_hi": (239, 211, 231),
    },
    "GENERAL SCIENCE": {
        "top": (7, 42, 48), "bottom": (10, 77, 74),
        "blob1": (54, 190, 170), "blob2": (126, 231, 203),
        "accent": (115, 238, 211), "accent2": (55, 197, 183),
        "card": (12, 57, 61), "card_outline": (89, 224, 202),
        "text": (245, 255, 253), "subtext": (187, 238, 225),
        "correct": (128, 219, 178), "correct_outline": (191, 255, 224),
        "correct_text": (7, 49, 43), "correct_hi": (24, 91, 76),
        "explanation": (7, 48, 49), "explanation_outline": (115, 238, 211),
        "explanation_title": (151, 248, 219), "explanation_text": (247, 255, 253),
        "explanation_hi": (187, 238, 225),
    },
    "GK": {
        "top": (11, 17, 39), "bottom": (30, 30, 70),
        "blob1": (40, 91, 145), "blob2": (198, 151, 58),
        "accent": (246, 198, 86), "accent2": (102, 165, 225),
        "card": (20, 28, 58), "card_outline": (92, 157, 224),
        "text": (255, 255, 255), "subtext": (210, 220, 241),
        "correct": (207, 165, 62), "correct_outline": (255, 222, 128),
        "correct_text": (31, 25, 13), "correct_hi": (76, 60, 25),
        "explanation": (17, 24, 50), "explanation_outline": (246, 198, 86),
        "explanation_title": (255, 213, 112), "explanation_text": (255, 255, 255),
        "explanation_hi": (210, 220, 241),
    },
    "MATH": {
        "top": (9, 28, 65), "bottom": (17, 62, 110),
        "blob1": (48, 132, 210), "blob2": (239, 132, 64),
        "accent": (255, 165, 78), "accent2": (89, 187, 255),
        "card": (15, 45, 86), "card_outline": (82, 178, 247),
        "text": (250, 253, 255), "subtext": (196, 225, 248),
        "correct": (240, 142, 66), "correct_outline": (255, 202, 137),
        "correct_text": (39, 28, 18), "correct_hi": (81, 53, 30),
        "explanation": (11, 38, 72), "explanation_outline": (255, 165, 78),
        "explanation_title": (255, 188, 104), "explanation_text": (250, 253, 255),
        "explanation_hi": (196, 225, 248),
    },
    "REASONING": {
        "top": (50, 15, 36), "bottom": (87, 27, 56),
        "blob1": (183, 65, 113), "blob2": (64, 181, 184),
        "accent": (94, 214, 211), "accent2": (235, 110, 157),
        "card": (61, 23, 50), "card_outline": (94, 214, 211),
        "text": (255, 252, 255), "subtext": (230, 202, 221),
        "correct": (90, 194, 177), "correct_outline": (163, 245, 225),
        "correct_text": (19, 52, 49), "correct_hi": (34, 91, 81),
        "explanation": (45, 19, 39), "explanation_outline": (94, 214, 211),
        "explanation_title": (119, 231, 225), "explanation_text": (255, 252, 255),
        "explanation_hi": (230, 202, 221),
    },
    "ALL SUBJECTS": {
        "top": (17, 20, 48), "bottom": (36, 33, 75),
        "blob1": (76, 126, 216), "blob2": (166, 93, 211),
        "accent": (116, 194, 255), "accent2": (201, 129, 239),
        "card": (28, 31, 68), "card_outline": (102, 183, 248),
        "text": (255, 255, 255), "subtext": (216, 221, 244),
        "correct": (119, 178, 231), "correct_outline": (182, 222, 255),
        "correct_text": (21, 39, 60), "correct_hi": (42, 70, 96),
        "explanation": (24, 27, 58), "explanation_outline": (116, 194, 255),
        "explanation_title": (157, 211, 255), "explanation_text": (255, 255, 255),
        "explanation_hi": (216, 221, 244),
    },
}


def _theme(subject):
    key = str(subject or "ALL SUBJECTS").strip().upper()
    if key in THEMES:
        return THEMES[key]
    return THEMES["ALL SUBJECTS"]


def _font(size: int, bold: bool = False, hindi: bool = False):
    candidates = []
    if hindi:
        candidates = [
            FONT_HI,
            Path("/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf"),
        ]
    else:
        candidates = [FONT_EN_BOLD if bold else FONT_EN]

    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(
                    str(path), size, layout_engine=ImageFont.Layout.RAQM
                )
            except Exception:
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _background(subject="ALL SUBJECTS"):
    key = str(subject or "ALL SUBJECTS").strip().upper()
    if key not in _BG_CACHE:
        theme = _theme(key)
        image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
        px = image.load()
        top, bottom = theme["top"], theme["bottom"]

        for y in range(VIDEO_HEIGHT):
            ratio = y / max(1, VIDEO_HEIGHT - 1)
            color = tuple(
                int(top[i] * (1 - ratio) + bottom[i] * ratio)
                for i in range(3)
            )
            for x in range(VIDEO_WIDTH):
                px[x, y] = color

        # Soft decorative shapes only. No lines, grids, or border/frame.
        decor = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(decor, "RGBA")
        d.ellipse((-165, -85, 295, 390), fill=(*theme["blob1"], 225))
        d.ellipse((430, 55, 850, 480), fill=(*theme["blob2"], 205))
        d.ellipse((-160, 1030, 170, 1360), fill=(*theme["blob2"], 125))
        d.ellipse((555, 1020, 850, 1330), fill=(*theme["blob1"], 125))
        decor = decor.filter(ImageFilter.GaussianBlur(0.8))
        image = Image.alpha_composite(image.convert("RGBA"), decor)
        _BG_CACHE[key] = image

    return _BG_CACHE[key].copy()


def _logo():
    global _LOGO
    if _LOGO is not None:
        return _LOGO

    source = Image.open(ASSETS_DIR / "logo.png").convert("RGBA")
    source = source.crop((90, 25, 380, 315))
    source.thumbnail((180, 180), Image.Resampling.LANCZOS)

    size = 205
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        (7, 9, size - 3, size - 3), fill=(0, 0, 0, 105)
    )
    badge.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    white.putalpha(mask)
    badge.alpha_composite(white)

    x = (size - source.width) // 2
    y = (size - source.height) // 2
    source_mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(source_mask).ellipse(
        (0, 0, source.width - 1, source.height - 1), fill=255
    )
    source.putalpha(source_mask)
    badge.alpha_composite(source, (x, y))
    _LOGO = badge
    return _LOGO


def _parts(value):
    if isinstance(value, dict):
        return str(value.get("en", "")).strip(), str(value.get("hi", "")).strip()
    return str(value or "").strip(), ""


def _question_parts(q):
    return _parts(q.get("question", ""))


def _option_parts(value):
    return _parts(value)


def _normalize_options(value, limit=4):
    if value is None:
        return []

    if isinstance(value, dict):
        en_values = value.get("en", [])
        hi_values = value.get("hi", [])
        en_values = list(en_values) if isinstance(en_values, (list, tuple)) else (
            [en_values] if en_values not in (None, "") else []
        )
        hi_values = list(hi_values) if isinstance(hi_values, (list, tuple)) else (
            [hi_values] if hi_values not in (None, "") else []
        )

        count = max(len(en_values), len(hi_values))
        return [
            {
                "en": en_values[i] if i < len(en_values) else "",
                "hi": hi_values[i] if i < len(hi_values) else "",
            }
            for i in range(min(count, limit))
        ]

    if isinstance(value, (list, tuple)):
        return list(value[:limit])

    return [value]


def _get_options(q, limit=4):
    if not isinstance(q, dict):
        return []
    return _normalize_options(q.get("options"), limit=limit)


def _is_hindi(text):
    return bool(DEVANAGARI_RE.search(str(text or "")))


def _runs(text):
    text = str(text or "").replace("\r", "").strip()
    if not text:
        return []

    result, current, state = [], "", None
    for ch in text:
        if ch.isspace():
            current += ch
            continue

        hindi = _is_hindi(ch)
        if state is None:
            state = hindi
        elif hindi != state:
            if current:
                result.append((current, state))
            current, state = "", hindi
        current += ch

    if current:
        result.append((current, bool(state)))
    return result


def _width(draw, text, size, bold=False, force_hindi=None):
    if force_hindi is not None:
        font = _font(size, bold=bold, hindi=force_hindi)
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    return sum(
        draw.textlength(run, font=_font(size, bold=bold, hindi=hindi))
        for run, hindi in _runs(text)
    )


def _wrap(draw, text, size, max_width, bold=False, force_hindi=None):
    words = re.findall(r"\S+|\s+", str(text or "").strip())
    lines, line = [], ""

    for token in words:
        if token.isspace():
            if line:
                line += " "
            continue

        candidate = token if not line else f"{line.rstrip()} {token}"
        if _width(draw, candidate, size, bold, force_hindi) <= max_width:
            line = candidate
            continue

        if line.strip():
            lines.append(line.strip())
            line = ""

        if _width(draw, token, size, bold, force_hindi) <= max_width:
            line = token
        else:
            chunk = ""
            for char in token:
                candidate = chunk + char
                if chunk and _width(draw, candidate, size, bold, force_hindi) > max_width:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = candidate
            line = chunk

    if line.strip():
        lines.append(line.strip())

    return lines


def _draw_line(draw, text, y, box, size, fill, bold=False, align="center", force_hindi=None):
    left, _, right, _ = box
    runs = [(str(text), force_hindi)] if force_hindi is not None else _runs(text)

    if not runs:
        return

    metrics, total = [], 0
    for run, hindi in runs:
        font = _font(size, bold=bold, hindi=bool(hindi))
        width = draw.textlength(run, font=font)
        bbox = draw.textbbox((0, 0), run, font=font)
        metrics.append((run, font, width, bbox))
        total += width

    if align == "left":
        x = left
    elif align == "right":
        x = right - total
    else:
        x = left + (right - left - total) / 2

    baseline = y + max(item[3][3] for item in metrics)
    for run, font, width, bbox in metrics:
        draw.text((x, baseline - bbox[3]), run, font=font, fill=fill)
        x += width


def _draw_fit(
    draw,
    text,
    box,
    fill,
    start,
    minimum,
    bold=False,
    force_hindi=None,
    gap=5,
    align="center",
):
    left, top, right, bottom = box
    for size in range(start, minimum - 1, -1):
        lines = _wrap(draw, text, size, right - left, bold, force_hindi)
        line_height = max(1, int(size * 1.18))
        needed = len(lines) * line_height + max(0, len(lines) - 1) * gap

        if needed <= bottom - top:
            y = top
            for line in lines:
                _draw_line(
                    draw, line, y, box, size, fill, bold, align, force_hindi
                )
                y += line_height + gap
            return y

    return top


def _draw_logo(image, y):
    logo = _logo()
    image.alpha_composite(logo, ((VIDEO_WIDTH - logo.width) // 2, y))


def _draw_option(draw, y, index, en, hi, height, theme, correct=False):
    left, right = 48, VIDEO_WIDTH - 48
    box = (left, y, right, y + height)

    fill = theme["correct"] if correct else theme["card"]
    outline = theme["correct_outline"] if correct else theme["card_outline"]

    draw.rounded_rectangle(
        box,
        radius=20,
        fill=fill,
        outline=outline,
        width=3,
    )

    # Marker and text are deliberately separated. The text starts 22px after
    # the marker's right edge, preventing "A.Hijri Era" style collisions.
    marker_x = left + 40
    marker_y = y + height // 2
    marker_radius = 18
    marker_fill = theme["accent"] if not correct else theme["correct_outline"]

    draw.ellipse(
        (
            marker_x - marker_radius,
            marker_y - marker_radius,
            marker_x + marker_radius,
            marker_y + marker_radius,
        ),
        fill=marker_fill,
    )

    draw.text(
        (marker_x, marker_y - 1),
        chr(65 + index),
        font=_font(19, bold=True),
        fill=(255, 255, 255) if not correct else theme["correct_text"],
        anchor="mm",
    )

    text_left = marker_x + marker_radius + 22
    text_right = right - 20

    main_fill = theme["correct_text"] if correct else theme["text"]
    hi_fill = theme["correct_hi"] if correct else theme["subtext"]

    if en:
        _draw_fit(
            draw,
            en,
            (text_left, y + 10, text_right, y + 58),
            main_fill,
            27,
            20,
            bold=correct,
            gap=1,
            align="left",
        )

    if hi and hi.casefold() != en.casefold():
        _draw_fit(
            draw,
            hi,
            (text_left, y + 57, text_right, y + height - 9),
            hi_fill,
            20,
            15,
            gap=1,
            align="left",
        )


def _draw_subject_badge(draw, subject, theme, y):
    label = {
        "ENGLISH": "ENGLISH",
        "GENERAL SCIENCE": "GENERAL SCIENCE",
        "GK": "GENERAL KNOWLEDGE",
        "MATH": "MATHEMATICS",
        "REASONING": "REASONING",
        "ALL SUBJECTS": "ALL SUBJECTS",
    }.get(str(subject or "").upper(), str(subject or "QUIZ").upper())

    box_w = min(460, max(190, int(_width(draw, label, 18, True) + 48)))
    x1 = (VIDEO_WIDTH - box_w) // 2
    x2 = x1 + box_w

    draw.rounded_rectangle(
        (x1, y, x2, y + 38),
        radius=19,
        fill=(*theme["accent"], 220),
    )
    draw.text(
        ((x1 + x2) // 2, y + 19),
        label,
        font=_font(18, bold=True),
        fill=(255, 255, 255),
        anchor="mm",
    )


def _draw_explanation(draw, q, theme, top, bottom):
    explanation = q.get("explanation", "")
    exp_en, exp_hi = _parts(explanation)
    if not exp_en and not exp_hi:
        return

    draw.rounded_rectangle(
        (42, top, VIDEO_WIDTH - 42, bottom),
        radius=22,
        fill=theme["explanation"],
        outline=theme["explanation_outline"],
        width=3,
    )

    # High-contrast title strip.
    draw.rounded_rectangle(
        (58, top + 12, 225, top + 48),
        radius=14,
        fill=theme["explanation_title"],
    )
    draw.text(
        (141, top + 30),
        "EXPLANATION",
        font=_font(15, bold=True),
        fill=theme["explanation"],
        anchor="mm",
    )

    ey = top + 61
    if exp_en:
        ey = _draw_fit(
            draw,
            exp_en,
            (65, ey, VIDEO_WIDTH - 65, bottom - 58 if exp_hi else bottom - 18),
            theme["explanation_text"],
            22,
            15,
            bold=True,
            gap=3,
            align="left",
        )

    if exp_hi and ey < bottom - 20:
        _draw_fit(
            draw,
            exp_hi,
            (65, ey + 4, VIDEO_WIDTH - 65, bottom - 15),
            theme["explanation_hi"],
            19,
            14,
            gap=2,
            align="left",
        )


def render_question(q, index, timer, output, subject="ALL SUBJECTS"):
    theme = _theme(subject)
    image = _background(subject)
    draw = ImageDraw.Draw(image, "RGBA")

    _draw_logo(image, 35)
    _draw_subject_badge(draw, subject, theme, 235)

    en, hi = _question_parts(q)

    if timer is not None:
        draw.text(
            (VIDEO_WIDTH // 2, 300),
            str(timer),
            font=_font(66, bold=True),
            fill=theme["accent"],
            anchor="mm",
        )
        question_top = 345
    else:
        question_top = 285

    # Compact question area leaves a guaranteed block for all four options.
    q_bottom = 455 if timer is not None else 440
    y = _draw_fit(
        draw,
        f"Q{index + 1}. {en}",
        (52, question_top, VIDEO_WIDTH - 52, q_bottom),
        theme["text"],
        40 if timer is None else 36,
        26,
        bold=True,
        gap=5,
        align="center",
    )

    if hi:
        y = _draw_fit(
            draw,
            hi,
            (60, y + 5, VIDEO_WIDTH - 60, 505),
            theme["subtext"],
            25,
            17,
            gap=3,
            align="center",
        )

    options = _get_options(q, 4)
    option_height = 103
    option_gap = 10
    option_start = 535 if timer is None else 550

    for i, option in enumerate(options):
        en_opt, hi_opt = _option_parts(option)
        _draw_option(
            draw,
            option_start + i * (option_height + option_gap),
            i,
            en_opt,
            hi_opt,
            option_height,
            theme,
        )

    draw.text(
        (VIDEO_WIDTH // 2, 1035),
        "Comment your answer!",
        font=_font(23, bold=True),
        fill=theme["accent"],
        anchor="mm",
    )

    draw.text(
        (VIDEO_WIDTH // 2, 1080),
        "Smart Learning Lab",
        font=_font(20, bold=True),
        fill=theme["text"],
        anchor="mm",
    )

    image.convert("RGB").save(output, quality=92, optimize=True)


def render_answer(q, index, output, subject="ALL SUBJECTS"):
    theme = _theme(subject)
    image = _background(subject)
    draw = ImageDraw.Draw(image, "RGBA")

    _draw_logo(image, 25)
    _draw_subject_badge(draw, subject, theme, 220)

    draw.text(
        (VIDEO_WIDTH // 2, 275),
        f"ANSWER — Q{index + 1}",
        font=_font(29, bold=True),
        fill=theme["accent"],
        anchor="mm",
    )

    en, hi = _question_parts(q)
    y = _draw_fit(
        draw,
        en,
        (50, 305, VIDEO_WIDTH - 50, 405),
        theme["text"],
        31,
        22,
        bold=True,
        gap=4,
        align="center",
    )

    if hi:
        y = _draw_fit(
            draw,
            hi,
            (60, y + 3, VIDEO_WIDTH - 60, 455),
            theme["subtext"],
            21,
            15,
            gap=2,
            align="center",
        )

    options = _get_options(q, 4)
    option_height = 86
    option_gap = 8
    option_start = 475

    for i, option in enumerate(options):
        en_opt, hi_opt = _option_parts(option)
        _draw_option(
            draw,
            option_start + i * (option_height + option_gap),
            i,
            en_opt,
            hi_opt,
            option_height,
            theme,
            correct=(i == q.get("answer_index")),
        )

    # Explanation gets its own fixed area below the four options, so it can
    # never be hidden behind an option or the bottom branding.
    _draw_explanation(draw, q, theme, 855, 1115)

    draw.text(
        (VIDEO_WIDTH // 2, 1170),
        "Smart Learning Lab",
        font=_font(21, bold=True),
        fill=theme["text"],
        anchor="mm",
    )
    draw.text(
        (VIDEO_WIDTH // 2, 1203),
        "Learn • Practice • Grow",
        font=_font(17, bold=True),
        fill=theme["subtext"],
        anchor="mm",
    )

    image.convert("RGB").save(output, quality=92, optimize=True)

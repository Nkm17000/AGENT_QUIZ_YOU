import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import ASSETS_DIR, VIDEO_HEIGHT, VIDEO_WIDTH

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F\u1CD0-\u1CFF\uA8E0-\uA8FF]")
FONT_EN = ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
FONT_EN_BOLD = ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
FONT_HI = ASSETS_DIR / "fonts" / "NotoSansDevanagari-Regular.ttf"

_BG = None
_LOGO = None


def _font(size: int, bold: bool = False, hindi: bool = False):
    candidates = []
    if hindi:
        candidates = [FONT_HI, Path("/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf")]
    else:
        candidates = [FONT_EN_BOLD if bold else FONT_EN]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _background():
    global _BG
    if _BG is None:
        top, bottom = (2, 13, 24), (10, 42, 67)
        image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
        px = image.load()
        for y in range(VIDEO_HEIGHT):
            ratio = y / max(1, VIDEO_HEIGHT - 1)
            color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            for x in range(VIDEO_WIDTH):
                px[x, y] = color
        _BG = image
    return _BG.copy().convert("RGBA")


def _logo():
    global _LOGO
    if _LOGO is not None:
        return _LOGO

    source = Image.open(ASSETS_DIR / "logo.png").convert("RGBA")
    # Crop the original white margin before fitting the mark into a circle.
    source = source.crop((90, 25, 380, 315))
    source.thumbnail((204, 204), Image.Resampling.LANCZOS)

    size = 230
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((8, 10, size - 2, size - 2), fill=(0, 0, 0, 90))
    badge.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    white.putalpha(mask)
    badge.alpha_composite(white)

    x = (size - source.width) // 2
    y = (size - source.height) // 2
    source_mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(source_mask).ellipse((0, 0, source.width - 1, source.height - 1), fill=255)
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
    """Normalize one option into (English, Hindi).

    Supported dataset shapes:
      1. {"en": "English", "hi": "Hindi"}
      2. "English"
    """
    return _parts(value)


def _normalize_options(value, limit=4):
    """Normalize all supported quiz option shapes to a list of option objects.

    Current question datasets use two schemas:
      - {"en": ["A", "B"], "hi": ["अ", "ब"]}
      - [{"en": "A", "hi": "अ"}, {"en": "B", "hi": "ब"}]

    The renderer should consume either shape without making assumptions about
    the source JSON format.
    """
    if value is None:
        return []

    # Schema: {"en": [...], "hi": [...]}
    if isinstance(value, dict):
        en_values = value.get("en", [])
        hi_values = value.get("hi", [])

        if isinstance(en_values, (list, tuple)):
            en_values = list(en_values)
        else:
            en_values = [en_values] if en_values not in (None, "") else []

        if isinstance(hi_values, (list, tuple)):
            hi_values = list(hi_values)
        else:
            hi_values = [hi_values] if hi_values not in (None, "") else []

        count = max(len(en_values), len(hi_values))
        normalized = []
        for i in range(count):
            normalized.append({
                "en": en_values[i] if i < len(en_values) else "",
                "hi": hi_values[i] if i < len(hi_values) else "",
            })
        return normalized[:limit]

    # Schema: [{"en": "...", "hi": "..."}, ...] or ["...", ...]
    if isinstance(value, (list, tuple)):
        return list(value[:limit])

    # Defensive fallback for malformed data.
    return [value]


def _get_options(q, limit=4):
    if not isinstance(q, dict):
        return []
    return _normalize_options(q.get("options"), limit=limit)


def _is_hindi(text):
    return bool(DEVANAGARI_RE.search(str(text or "")))


def _runs(text):
    """Split text into Unicode-script runs so mixed Hindi + English works.

    Hindi/Devanagari runs use Noto Sans Devanagari, while Latin/number/punctuation
    runs use DejaVu Sans. This must be used for every learner-visible string;
    forcing an entire mixed string through an English-only font creates tofu boxes.
    """
    text = str(text or "").replace("\r", "").strip()
    if not text:
        return []
    result = []
    current = ""
    state = None
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
    return sum(draw.textlength(run, font=_font(size, bold=bold, hindi=hindi)) for run, hindi in _runs(text))


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
    metrics = []
    total = 0
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


def _draw_fit(draw, text, box, fill, start, minimum, bold=False, force_hindi=None, gap=5, align="center"):
    left, top, right, bottom = box
    for size in range(start, minimum - 1, -1):
        lines = _wrap(draw, text, size, right - left, bold, force_hindi)
        line_height = max(1, int(size * 1.18))
        needed = len(lines) * line_height + max(0, len(lines) - 1) * gap
        if needed <= bottom - top:
            y = top
            for line in lines:
                _draw_line(draw, line, y, box, size, fill, bold, align, force_hindi)
                y += line_height + gap
            return y
    return top


def _draw_logo(image, y):
    logo = _logo()
    image.alpha_composite(logo, ((VIDEO_WIDTH - logo.width) // 2, y))


def _draw_option(draw, y, index, en, hi, height, correct=False):
    box = (70, y, VIDEO_WIDTH - 70, y + height)
    draw.rounded_rectangle(
        box,
        radius=16,
        fill=(0, 214, 142) if correct else (18, 43, 62),
        outline=(0, 255, 157) if correct else (0, 195, 255),
        width=2,
    )
    main_fill = "black" if correct else "white"
    hi_fill = "#1a1a1a" if correct else "#b3d9ff"
    _draw_fit(
        draw,
        f"{chr(65 + index)}. {en}",
        (105, y + 10, VIDEO_WIDTH - 105, y + height // 2 + 2),
        main_fill,
        30,
        20,
        bold=correct,
        gap=1,
        align="left",
        force_hindi=None,
    )
    if hi and hi.casefold() != en.casefold():
        _draw_fit(
            draw,
            hi,
            (105, y + height // 2, VIDEO_WIDTH - 105, y + height - 8),
            hi_fill,
            22,
            15,
            gap=1,
            align="left",
            force_hindi=None,
        )


def render_question(q, index, timer, output):
    image = _background()
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_logo(image, 115)

    if timer is not None:
        draw.text(
            (VIDEO_WIDTH // 2, 390),
            str(timer),
            font=_font(76, bold=True),
            fill=(255, 204, 0),
            anchor="mm",
        )

    en, hi = _question_parts(q)
    y = 470 if timer is not None else 390
    y = _draw_fit(
        draw,
        f"Q{index + 1}. {en}",
        (65, y, VIDEO_WIDTH - 65, 760),
        "white",
        48,
        34,
        bold=True,
        gap=7,
        align="center",
        force_hindi=None,
    )
    if hi:
        y += 10
        y = _draw_fit(
            draw,
            hi,
            (75, y, VIDEO_WIDTH - 75, 880),
            "#cce6ff",
            31,
            21,
            gap=4,
            align="center",
            force_hindi=None,
        )

    options = _get_options(q, 4)
    option_height, option_gap = 132, 14
    total = len(options) * option_height + max(0, len(options) - 1) * option_gap
    option_start = max(955, int(y + 25))
    option_start = min(option_start, 1745 - total)
    for i, option in enumerate(options):
        en_opt, hi_opt = _option_parts(option)
        _draw_option(draw, option_start + i * (option_height + option_gap), i, en_opt, hi_opt, option_height)

    draw.text(
        (VIDEO_WIDTH // 2, 1810),
        "Comment your answer!",
        font=_font(26, bold=True),
        fill="#00ff9d",
        anchor="mm",
    )
    image.convert("RGB").save(output, quality=92, optimize=True)


def render_answer(q, index, output):
    image = _background()
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_logo(image, 75)

    en, hi = _question_parts(q)
    # Answer slides are not additional questions.  Make that explicit in the
    # visual header so the video cannot be mistaken for a 40-question quiz.
    draw.text(
        (VIDEO_WIDTH // 2, 315),
        f"ANSWER — Q{index + 1}",
        font=_font(34, bold=True),
        fill="#ffcc00",
        anchor="mm",
    )
    y = _draw_fit(draw, en, (65, 365, VIDEO_WIDTH - 65, 575), "white", 43, 31, bold=True, gap=6, force_hindi=None)
    if hi:
        y += 8
        y = _draw_fit(draw, hi, (75, y, VIDEO_WIDTH - 75, 680), "#cce6ff", 28, 19, gap=4, force_hindi=None)

    options = _get_options(q, 4)
    option_height, option_gap = 112, 10
    option_start = max(710, int(y + 18))
    total = len(options) * option_height + max(0, len(options) - 1) * option_gap
    option_start = min(option_start, 1680 - total)
    oy = option_start
    for i, option in enumerate(options):
        en_opt, hi_opt = _option_parts(option)
        _draw_option(draw, oy, i, en_opt, hi_opt, option_height, correct=(i == q.get("answer_index")))
        oy += option_height + option_gap

    explanation = q.get("explanation", "")
    exp_en, exp_hi = _parts(explanation)
    if exp_en or exp_hi:
        top = min(1700, oy + 10)
        bottom = min(1765, top + 190)
        if bottom > top + 30:
            draw.rounded_rectangle((70, top, VIDEO_WIDTH - 70, bottom), radius=15, fill=(38, 37, 25), outline=(255, 204, 0), width=2)
            ey = top + 16
            if exp_en:
                ey = _draw_fit(draw, exp_en, (95, ey, VIDEO_WIDTH - 95, bottom - 75), "#ffcc00", 24, 17, gap=3, align="left", force_hindi=None)
            if exp_hi and ey < bottom - 18:
                _draw_fit(draw, exp_hi, (95, ey + 3, VIDEO_WIDTH - 95, bottom - 12), "#ffe599", 21, 15, gap=2, align="left", force_hindi=None)

    draw.text((VIDEO_WIDTH // 2, 1810), "By Nitin Mittal Innovations", font=_font(22, bold=True), fill="#b9cfe1", anchor="mm")
    image.convert("RGB").save(output, quality=92, optimize=True)

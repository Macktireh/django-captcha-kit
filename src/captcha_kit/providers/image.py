"""
Local image CAPTCHA: distorted characters rendered with Pillow, no third-party
service, no network call.

The token scheme (keyed digest, expiry, single use) lives in
:class:`~captcha_kit.providers.signed.SignedChallengeProvider`. This module
draws the challenge text and inlines the PNG as a ``data:`` URI, so the
package still ships no view and no URL: the image travels inside the form
HTML, and only the signed token comes back with the answer.

Pillow is deliberately imported inside ``__init__``: the registry imports this
module even when the provider is never used, and the core package must stay
importable with Django alone.
"""

from __future__ import annotations

import base64
import io
import math
import random
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .signed import SignedChallengeProvider

DEFAULT_FONT = Path(__file__).resolve().parent.parent / "fonts" / "Vera.ttf"

# Drawn at twice the requested size then downscaled: cheap anti-aliasing that
# also smears the per-character edges OCR segmentation keys on.
SUPERSAMPLE = 2

# Palette size of the encoded PNG. See the note in _draw.
PALETTE_COLOURS = 64

# Stroke width of the glyphs, as a fraction of the canvas height, for the font
# sizes drawn below. The noise strokes match it so that no filter can tell the
# two apart. Measured on Bitstream Vera; close enough for any sans-serif.
STROKE_RATIO = 0.045


class ImageCaptchaProvider(SignedChallengeProvider):
    """
    Local Image Captcha, verified without contacting any external service.

    The challenge text and the expected answer are the same string; the
    obfuscation happens entirely at draw time (per-character rotation and
    overlap, noise arcs, global shear), so the token machinery inherited from
    :class:`SignedChallengeProvider` never has to know about pixels.

    Supported options (upper-cased in ``CAPTCHA_KIT['PROVIDERS']``):

    ``LENGTH``
        Number of characters in the challenge, at least ``6``. Defaults to
        ``6``, which is already 21**6 ≈ 85 million answers with the default
        alphabet; length buys far less than the single-use guard does.
    ``ALPHABET``
        Characters the challenge may use. The default drops every glyph that
        becomes ambiguous once rotated and noisy (``0/O/o``, ``1/l/I``,
        ``5/S``, ``8/B``, ``9/g/q``, ``2/z``, ``u/v``), and sticks to
        lowercase since verification is case-insensitive anyway.
    ``WIDTH`` / ``HEIGHT``
        Size of the rendered image, in pixels. Default to ``260`` × ``80``,
        sized so the default six characters stay comfortably legible. Raising
        ``LENGTH`` without widening the image shrinks the word to fit.
    ``FONT_PATHS``
        TrueType files to pick from, one at random per character. Defaults to
        the bundled Bitstream Vera.
    ``MAX_AGE``, ``SINGLE_USE``, ``CACHE_ALIAS``, ``TEMPLATE_NAME``
        Inherited from the signed-challenge base; template defaults to
        ``"captcha_kit/image.html"``.
    """

    template_name = "captcha_kit/image.html"
    salt = "captcha_kit.providers.image"

    def __init__(self, **options) -> None:
        try:
            import PIL.Image  # noqa: F401
        except ImportError as exc:
            raise ImproperlyConfigured(
                f"{type(self).__name__} requires Pillow. Install it with "
                "'pip install django-captcha-kit[image]'."
            ) from exc

        super().__init__(**options)
        self.length = int(options.get("length", 6))
        self.alphabet = str(options.get("alphabet", "acdefhkmnprtwxy234678"))
        self.width = int(options.get("width", 260))
        self.height = int(options.get("height", 80))
        self.font_paths = [str(path) for path in options.get("font_paths") or [DEFAULT_FONT]]

        if self.length < 6:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: LENGTH must be at least 6, got {self.length}."
            )
        if len(set(self.alphabet.casefold())) < 2:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: ALPHABET needs at least 2 distinct "
                f"case-insensitive characters, got {self.alphabet!r}."
            )
        if self.width < 50:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: WIDTH must be at least 50, got {self.width}."
            )
        if self.height < 20:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: HEIGHT must be at least 20, got {self.height}."
            )
        missing = [path for path in self.font_paths if not Path(path).is_file()]
        if missing:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: FONT_PATHS lists missing files: {missing}."
            )

    def _challenge(self) -> tuple[str, str]:
        """The public challenge and the answer are the same string of characters."""
        text = "".join(secrets.choice(self.alphabet) for _ in range(self.length))
        return text, text

    def _render_context(self, challenge) -> dict:
        return {
            "image": self._data_uri(challenge),
            "width": self.width,
            "height": self.height,
        }

    @staticmethod
    def _normalise(answer: str) -> str:
        """Casefold on both sides of the digest, making verification case-insensitive."""
        return answer.strip().casefold()

    def _data_uri(self, text: str) -> str:
        return "data:image/png;base64," + base64.b64encode(self._draw(text)).decode("ascii")

    def _draw(self, text: str) -> bytes:
        """
        Render the challenge as PNG bytes.

        Only the challenge text needs cryptographic randomness (and gets it,
        in :meth:`_challenge`); the visual noise below uses a local
        ``random.Random`` so drawing never touches the global RNG state.
        """
        from PIL import Image

        rng = random.Random()
        w, h = self.width * SUPERSAMPLE, self.height * SUPERSAMPLE
        background = tuple(rng.randint(235, 255) for _ in range(3))
        image = Image.new("RGB", (w, h), background)

        # One ink for the whole challenge. Giving each character its own colour
        # looks nicer but hands an attacker free segmentation: cluster by hue
        # and the overlapping glyphs come apart again.
        ink = tuple(rng.randint(0, 90) for _ in range(3))
        stroke = max(int(STROKE_RATIO * h), 2)

        # The shear below slides the bottom of the image sideways by shear * h,
        # so the text is inset by that much: a clipped glyph is unreadable, and
        # an unreadable challenge locks out the legitimate user, not the bot.
        shear = rng.uniform(-0.12, 0.12)
        # Capped at a third of the width: on a tall, narrow canvas the shear
        # margin would otherwise be wider than the image itself.
        inset_x = min(int(abs(shear) * h) + w // 20, w // 3)
        inset_y = h // 8  # the warp displaces vertically too

        block = self._text_block(text, h, rng, ink)
        block = self._fit(block, w - 2 * inset_x, h - 2 * inset_y)
        image.paste(block, ((w - block.width) // 2, (h - block.height) // 2), block)

        # Noise first, warp second: a straight line is trivially found and
        # erased, a line bent by the same displacement as the glyphs is not.
        self._add_noise(image, rng, ink, stroke)
        image = self._warp(image, rng, background)

        image = image.transform(
            (w, h),
            Image.AFFINE,
            (1, shear, 0, 0, 1, 0),
            resample=Image.BICUBIC,
            fillcolor=background,
        )

        image = image.resize((self.width, self.height), Image.LANCZOS)

        # Anti-aliased strokes over a jittered background give almost every
        # pixel its own RGB triple, which is what a truecolour PNG encodes
        # badly. A 64-entry palette is visually indistinguishable here and
        # divides the inlined data URI by about three.
        image = image.convert("P", palette=Image.ADAPTIVE, colors=PALETTE_COLOURS)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    @staticmethod
    def _warp(image, rng: random.Random, fill):
        """
        Displace the finished image along two sine waves.

        This is the one distortion a preprocessing filter cannot undo. Specks
        and hairlines are removed by a 3x3 median filter in a single pass, but
        a geometric warp changes the shape of the glyphs themselves, so
        template matching and trained classifiers both have to cope with it.
        """
        from PIL import Image

        w, h = image.size
        cols, rows = 12, 5
        amplitude_x = w * rng.uniform(0.008, 0.016)
        amplitude_y = h * rng.uniform(0.035, 0.065)
        freq_x, freq_y = rng.uniform(1.1, 2.0), rng.uniform(1.1, 2.0)
        phase_x, phase_y = rng.uniform(0, math.tau), rng.uniform(0, math.tau)

        def source(x: float, y: float) -> tuple[float, float]:
            return (
                x + amplitude_x * math.sin(math.tau * freq_x * y / h + phase_x),
                y + amplitude_y * math.sin(math.tau * freq_y * x / w + phase_y),
            )

        # Shared vertices between neighbouring cells, otherwise the warp tears.
        mesh = []
        for row in range(rows):
            for col in range(cols):
                x0, x1 = col * w / cols, (col + 1) * w / cols
                y0, y1 = row * h / rows, (row + 1) * h / rows
                quad = (*source(x0, y0), *source(x0, y1), *source(x1, y1), *source(x1, y0))
                box = (int(x0), int(y0), math.ceil(x1), math.ceil(y1))
                mesh.append((box, quad))

        return image.transform((w, h), Image.MESH, mesh, resample=Image.BICUBIC, fillcolor=fill)

    def _text_block(self, text: str, canvas_height: int, rng: random.Random, ink):
        """
        Lay the rotated character tiles out on their own transparent layer.

        Composing the whole word first is what lets :meth:`_fit` scale it as a
        unit, so jitter and rotation can never push a glyph off the canvas.
        """
        from PIL import Image

        tiles = [self._char_tile(char, canvas_height, rng, ink) for char in text]

        # Glyphs are made to touch and overlap. Segmentation, not recognition,
        # is the hard half of reading a CAPTCHA: isolated characters are a
        # solved problem, joined ones are not.
        advances = [int(tile.width * rng.uniform(0.74, 0.88)) for tile in tiles[:-1]]
        offsets = []
        x = 0
        for index, _tile in enumerate(tiles):
            offsets.append((x, int(rng.uniform(-0.12, 0.12) * canvas_height)))
            if index < len(advances):
                x += advances[index]

        placed = list(zip(offsets, tiles, strict=True))
        top = min(y for _, y in offsets)
        width = max(x + tile.width for (x, _), tile in placed)
        height = max(y + tile.height for (_, y), tile in placed) - top

        block = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for (x, y), tile in placed:
            block.paste(tile, (x, y - top), tile)
        return block

    @staticmethod
    def _fit(block, max_width: int, max_height: int):
        """Shrink the word if jitter and rotation made it outgrow the canvas."""
        from PIL import Image

        scale = min(max_width / block.width, max_height / block.height, 1)
        if scale == 1:
            return block
        size = (max(int(block.width * scale), 1), max(int(block.height * scale), 1))
        return block.resize(size, Image.LANCZOS)

    def _char_tile(self, char: str, canvas_height: int, rng: random.Random, ink):
        """One character on its own transparent tile, coloured and rotated."""
        from PIL import Image, ImageDraw, ImageFont

        # Sized well under the canvas height: rotation expands the tile, and
        # leaving that headroom keeps _fit from having to shrink the whole word.
        font = ImageFont.truetype(
            rng.choice(self.font_paths), int(rng.uniform(0.45, 0.62) * canvas_height)
        )
        left, top, right, bottom = font.getbbox(char)
        tile = Image.new("RGBA", (max(right - left, 1), max(bottom - top, 1)), (0, 0, 0, 0))
        colour = self._shade(ink, rng)
        ImageDraw.Draw(tile).text((-left, -top), char, font=font, fill=colour + (255,))
        return tile.rotate(rng.uniform(-28, 28), expand=True, resample=Image.BICUBIC)

    @staticmethod
    def _shade(ink, rng: random.Random) -> tuple[int, int, int]:
        """
        A small variation on the challenge ink.

        Enough for the eye to tell strokes apart, too little for an attacker to
        cluster the pixels by colour and recover the character boundaries. The
        ceiling keeps every mark dark against the light background.
        """
        return tuple(min(max(channel + rng.randint(-30, 30), 0), 125) for channel in ink)

    def _add_noise(self, image, rng: random.Random, ink, stroke: int) -> None:
        """
        Strokes crossing the text, drawn in the challenge ink at the width of
        the glyph stems.

        Thin, pale noise is free to remove: one median pass and it is gone,
        because it does not look like a letter. Noise that matches the strokes
        it hides among cannot be filtered without taking the letters with it.
        """
        from PIL import ImageDraw

        w, h = image.size
        draw = ImageDraw.Draw(image)
        width = max(int(stroke * 0.6), 2)

        for _ in range(rng.randint(1, 2)):
            box = (
                rng.randint(-w // 4, w // 2),
                rng.randint(-h, h // 2),
                rng.randint(w // 2, w + w // 4),
                rng.randint(h // 2, 2 * h),
            )
            start = rng.randint(0, 360)
            end = start + rng.randint(90, 270)
            draw.arc(box, start, end, fill=self._shade(ink, rng), width=width)

        ends = (rng.randint(0, w // 4), rng.randint(0, h))
        ends += (rng.randint(3 * w // 4, w), rng.randint(0, h))
        draw.line(ends, fill=self._shade(ink, rng), width=width)

        # A light speckle, kept sparse on purpose: it costs a quarter of the
        # encoded size and a 3x3 median filter erases all of it, so it only
        # ever deters a bot that does no preprocessing at all.
        for _ in range((w * h) // 6000):
            xy = (rng.randint(0, w - 1), rng.randint(0, h - 1))
            draw.point(xy, fill=self._shade(ink, rng))

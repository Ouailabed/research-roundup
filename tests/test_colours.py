"""The tag colours must stay readable, and the same everywhere: the site in light and dark mode, the 3D map and the newsletter."""
import re

from src.config import ROOT

SITE = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
NEWSLETTER = (ROOT / "templates" / "newsletter.html").read_text(encoding="utf-8")
TAGS = ("EM", "DM", "Transversal")


def luminance(colour):
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, two):
    """The WCAG contrast ratio, from 1 (no contrast) to 21 (black on white)."""
    lighter, darker = sorted((luminance(one), luminance(two)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def tokens_after(marker):
    """The colour tokens in the first :root block after the marker."""
    start = SITE.index(":root {", SITE.index(marker))
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", SITE[start:SITE.index("}", start)]))


LIGHT = tokens_after("<style>")
# Dark mode changes some tokens and keeps the rest.
DARK = {**LIGHT, **tokens_after("@media (prefers-color-scheme: dark)")}


def test_text_on_each_tag_passes_aa_in_light_and_dark_mode():
    for mode in (LIGHT, DARK):
        for tag in TAGS:
            assert contrast(mode["on-mark"], mode[tag]) >= 4.5, tag


def test_tag_bars_stand_out_from_the_cards_in_light_and_dark_mode():
    for mode in (LIGHT, DARK):
        for tag in TAGS:
            assert contrast(mode[tag], mode["surface"]) >= 3, tag


def test_white_text_on_each_newsletter_tag_passes_aa():
    text = re.search(r"\.tag \{[^}]*color: (#[0-9a-fA-F]{6})", NEWSLETTER).group(1)
    for tag in TAGS:
        background = re.search(r"\.tag-" + tag + r" \{ background: (#[0-9a-fA-F]{6}); \}", NEWSLETTER).group(1)
        assert contrast(text, background) >= 4.5, tag


def test_the_newsletter_uses_the_same_tag_colours_as_the_light_site():
    newsletter = dict(re.findall(r"\.tag-(\w+) \{ background: (#[0-9a-fA-F]{6}); \}", NEWSLETTER))
    assert newsletter == {tag: LIGHT[tag] for tag in TAGS}


def test_the_3d_map_uses_the_dark_mode_tag_colours_and_they_show_on_the_header():
    # The header band is dark in both themes, so the map's dots use the dark-mode colours.
    dots = dict(re.findall(r"(\w+): glow\('(#[0-9a-fA-F]{6})'\)", SITE))
    assert dots == {tag: DARK[tag] for tag in TAGS}
    for band in (LIGHT["mast"], DARK["mast"]):
        for tag in TAGS:
            assert contrast(dots[tag], band) >= 3, tag

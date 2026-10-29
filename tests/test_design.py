from __future__ import annotations

import re

from weekglass.cli import analyze
from weekglass.report import render_html

from .conftest import make_config, simple_ics, vevent


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(a: str, b: str) -> float:
    first, second = luminance(a), luminance(b)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def render_demo(tmp_path):
    path = simple_ics(tmp_path, "work.ics", vevent(uid="a", start="20261026T100000", end="20261026T110000"))
    cfg = make_config()
    report, _s, _p = analyze([str(path)], cfg)
    return render_html(report, cfg, None)


def test_token_contrast_meets_aa(tmp_path):
    html = render_demo(tmp_path)
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    light = style.split(":root {", 1)[1].split("}", 1)[0]
    dark = style.split("@media (prefers-color-scheme: dark) {", 1)[1].split("}", 1)[0]

    def tokens(block):
        return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})", block))

    for block in (light, dark):
        t = tokens(block)
        assert contrast(t["ink"], t["bg"]) >= 4.5
        assert contrast(t["muted"], t["bg"]) >= 4.5
        assert contrast(t["faint"], t["bg"]) >= 4.5
        assert contrast(t["accent"], t["bg"]) >= 4.5
        assert contrast(t["warn"], t["bg"]) >= 4.5
        assert contrast(t["danger"], t["bg"]) >= 4.5
        assert contrast(t["accent-ink"], t["accent-wash"]) >= 4.5


def test_no_hardcoded_colours_or_font_sizes_outside_tokens(tmp_path):
    html = render_demo(tmp_path)
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    without_roots = re.sub(r":root\s*\{.*?\}", "", style, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}", without_roots)
    for value in re.findall(r"font-size:\s*([^;]+);", without_roots):
        assert value.strip().startswith("var("), value
    assert "linear-gradient" not in style
    assert "box-shadow:" not in without_roots


def test_no_script_or_external_resources(tmp_path):
    html = render_demo(tmp_path)
    assert "<script" not in html
    assert "<link" not in html
    assert "<img" not in html
    assert "<iframe" not in html
    assert "http://" not in html
    assert "https://" not in html

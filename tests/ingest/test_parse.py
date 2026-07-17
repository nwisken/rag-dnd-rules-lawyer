"""Tests parsing SRD markdown into Sections"""

import pytest

from ruleslawyer.ingest.parse import parse_markdown
from ruleslawyer.ingest.types import Section


def test_heading_with_no_body_is_emitted_empty() -> None:
    """checks a pure container heading still produces a section, with empty text"""
    result = parse_markdown("# Combat\n## Order of Combat\nbody text")
    assert result == [
        Section(heading_path=("Combat",), text=""),
        Section(heading_path=("Combat", "Order of Combat"), text="body text"),
    ]


def test_closing_hashes_are_stripped() -> None:
    """checks '## Combat ##' style headings lose the trailing hashes"""
    result = parse_markdown("## Combat ##\nsome text")
    assert result == [Section(heading_path=("Combat",), text="some text")]


def test_text_before_any_heading_gets_empty_path() -> None:
    """checks preamble text (license notice etc.) is kept, with an empty path"""
    result = parse_markdown("just some license preamble")
    assert result == [Section(heading_path=(), text="just some license preamble")]


def test_six_level_nesting_with_siblings() -> None:
    """checks the stack pops siblings at the same level and multi-pops on the way up"""
    md = "\n".join([
        "# L1",
        "## L2a",
        "### L3a",
        "text a",
        "### L3b",
        "text b",
        "#### L4",
        "##### L5",
        "###### L6",
        "deep text",
        "## L2b",
        "back up text",
    ])

    result = parse_markdown(md)

    assert [section.heading_path for section in result] == [
        ("L1",),
        ("L1", "L2a"),
        ("L1", "L2a", "L3a"),
        ("L1", "L2a", "L3b"),
        ("L1", "L2a", "L3b", "L4"),
        ("L1", "L2a", "L3b", "L4", "L5"),
        ("L1", "L2a", "L3b", "L4", "L5", "L6"),
        ("L1", "L2b"),
    ]
    assert [section.text for section in result] == [
        "", "", "text a", "text b", "", "", "deep text", "back up text",
    ]


@pytest.mark.xfail(
    reason="parser has no code-fence awareness; SRD corpus contains no fences",
    strict=True,
)
def test_hash_inside_code_fence_is_not_a_heading() -> None:
    """documents the known limitation: a '#' line inside ``` fences is misparsed"""
    md = "# Real Heading\n```\n# not a heading\n```\nafter the fence"
    result = parse_markdown(md)
    assert result == [
        Section(
            heading_path=("Real Heading",),
            text="```\n# not a heading\n```\nafter the fence",
        ),
    ]

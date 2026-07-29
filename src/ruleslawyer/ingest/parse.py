"""Parse SRD markdown into Sections via a heading-stack walk."""

import re

from ruleslawyer.ingest.types import Section

# Matches an ATX heading line and captures its level and title:
#   ^(#{1,6})   1-6 leading hashes (markdown's only levels); len() of this = level
#   \s+         at least one space required, so "#5 gold pieces" is NOT a heading
#                (this is CommonMark's rule too)
#   (.*?)       the title, non-greedy so trailing junk goes to the patterns below
#   \s*#*\s*$   optional closing hashes ("## Combat ##" -> title "Combat")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

# TODO KNOWN LIMITATION (measured, deliberately not fixed) -- the heading stack assumes a
# heading's children are all its descendants until a sibling or shallower heading
# appears. That holds for the SRD's rules chapters but not its monster catalogue,
# which uses two heading shapes this parser cannot tell apart:
#
#   1. Open-ended family groupings. "## Giants" holds six real giants, then
#      "### Gibbering Mouther" follows with no new "##" to close the group, so every
#      later G-monster inherits it -> "Monsters (G) > Giants > Goblin".
#   2. Groupings at the same level as their members. "## Dragons, Chromatic" is
#      followed by "## Black Dragon", so the grouping is popped immediately and the
#      36 dragon entries lose it entirely.
#
# Impact measured on SRD 5.1: 38 of 201 stat-block entries carry a family they do not
# belong to (~40 chunks, 1.56% of corpus text); case 2 loses a level rather than
# adding a wrong one, which is harmless by comparison. Not fixed because both cases
# are confined to monster stat blocks, no golden-set question grounds there, and any
# general rule would have to guess which heading shape a "##" means. Phase 2 tests
# indexing with and without stat blocks, which subsumes this.


def parse_markdown(md: str) -> list[Section]:
    """Split markdown into one Section per heading, tracking the outline path.

    Every heading emits a Section, even with no body text; the chunker's
    empty-text guard drops those downstream.

    Args:
        md: the full markdown document as one string.

    Returns:
        One Section per heading (plus one for any preamble before the first
        heading), in document order, each carrying its full heading_path.
    """
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, title), root -> current
    buffer: list[str] = []

    def flush() -> None:
        """Emit the buffered text under the current stack path as a Section."""
        path = tuple(title for _, title in stack)
        text = "\n".join(buffer).strip()
        if stack or text:
            sections.append(Section(heading_path=path, text=text))
        buffer.clear()

    for line in md.splitlines():
        match = HEADING_RE.match(line)
        if match is None:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, match.group(2)))
    flush()
    return sections

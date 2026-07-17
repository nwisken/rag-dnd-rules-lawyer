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

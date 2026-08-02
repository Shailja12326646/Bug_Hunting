"""
Code Parser Agent
-----------------
Parses raw C++ code strings into numbered lines for LLM analysis.
"""


def parse_code(code: str) -> list[tuple[int, str]]:
    """
    Split C++ code into (line_number, line_content) tuples.
    Line numbers start at 1.
    """
    lines = code.split('\n')
    return [(i + 1, line) for i, line in enumerate(lines)]


def format_numbered_code(numbered_lines: list[tuple[int, str]]) -> str:
    """
    Format numbered lines into a string for LLM prompt injection.
    Example output:
        Line 1: RDI_BEGIN();
        Line 2: rdi.dc().pin("dig").vForce(1 V).execute();
    """
    return '\n'.join([f"Line {num}: {line}" for num, line in numbered_lines])

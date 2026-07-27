from __future__ import annotations

from pathlib import Path


CANDIDATE_TABLE_CSS = """

/* Commercial report: keep the candidate list compact and scrollable. */
.candidate-table-wrap {
    --candidate-row-height: 54px;
    --candidate-header-height: 49px;
    max-height: calc(
        var(--candidate-header-height)
        + (var(--candidate-row-height) * var(--candidate-visible-rows, 10))
    );
    overflow-x: auto;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
}

.candidate-table-wrap thead th {
    position: sticky;
    top: 0;
    z-index: 3;
    background: #28134d;
    box-shadow: 0 1px 0 rgba(246, 246, 246, 0.18);
}

.candidate-table-wrap tbody tr {
    height: var(--candidate-row-height);
}

.candidate-table-wrap td {
    white-space: nowrap;
}

.candidate-table-wrap td:nth-child(1),
.candidate-table-wrap td:nth-child(2) {
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
}
"""


def add_candidate_table_scroll(
    report_path: str | Path,
    visible_rows: int = 10,
) -> Path:
    """Add a fixed-height scroll area to the Active Candidates table."""
    if visible_rows < 1:
        raise ValueError("visible_rows must be at least 1.")

    html_path = Path(report_path)

    if not html_path.exists():
        raise FileNotFoundError(f"HTML report not found: {html_path}")

    html = html_path.read_text(encoding="utf-8")

    section_marker = '<section id="candidates" class="section">'
    section_start = html.find(section_marker)

    if section_start == -1:
        raise RuntimeError(
            "Could not find the Active Candidates section in the generated HTML."
        )

    section_end = html.find("</section>", section_start)

    if section_end == -1:
        raise RuntimeError(
            "The Active Candidates section is missing its closing tag."
        )

    candidate_section = html[section_start:section_end]
    table_marker = '<div class="table-wrap">'

    if table_marker not in candidate_section:
        raise RuntimeError(
            "Could not find the candidates table wrapper in the generated HTML."
        )

    scrollable_table = (
        '<div class="table-wrap candidate-table-wrap" '
        f'style="--candidate-visible-rows: {visible_rows};">'
    )

    candidate_section = candidate_section.replace(
        table_marker,
        scrollable_table,
        1,
    )

    original_description = (
        "Candidate-level view for the currently open job titles."
    )
    scroll_description = (
        "Candidate-level view for the currently open job titles. "
        f"Showing {visible_rows} rows at a time; scroll to view the full list."
    )

    candidate_section = candidate_section.replace(
        original_description,
        scroll_description,
        1,
    )

    html = (
        html[:section_start]
        + candidate_section
        + html[section_end:]
    )

    if CANDIDATE_TABLE_CSS not in html:
        style_end = html.find("</style>")

        if style_end == -1:
            raise RuntimeError(
                "Could not find the report style block in the generated HTML."
            )

        html = (
            html[:style_end]
            + CANDIDATE_TABLE_CSS
            + "\n"
            + html[style_end:]
        )

    html_path.write_text(html, encoding="utf-8")

    return html_path

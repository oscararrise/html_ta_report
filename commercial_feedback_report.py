from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, select_autoescape

from generate_report import (
    build_hires_by_month_rows,
    build_report_context,
    prepare_requisitions,
)


BASE_DIR = Path(__file__).resolve().parent
REPORT_TEMPLATE = (
    BASE_DIR / "templates" / "commercial_executive_report_compact.html"
).read_text(encoding="utf-8")

def _month_bounds(reference: datetime) -> tuple[pd.Timestamp, pd.Timestamp]:
    current = pd.Timestamp(reference)
    start = current.normalize().replace(day=1)
    next_month = start + pd.offsets.MonthBegin(1)
    return start, next_month


def _to_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None

    try:
        if isinstance(value, (int, float)):
            return pd.to_datetime(value, unit="ms", utc=True)

        text = str(value).strip()
        if not text:
            return None

        if text.isdigit():
            return pd.to_datetime(int(text), unit="ms", utc=True)

        return pd.to_datetime(text, utc=True)
    except (TypeError, ValueError, OverflowError):
        return None


def _clean_value(value: Any, default: str = "--") -> str:
    if value is None or pd.isna(value):
        return default

    text = str(value).strip()
    return text or default


def get_hires_current_month(
    hired_people: pd.DataFrame,
    reference: datetime,
) -> list[dict[str, Any]]:
    if hired_people.empty or "app_hire_date" not in hired_people.columns:
        return []

    start, next_month = _month_bounds(reference)
    dates = pd.to_datetime(hired_people["app_hire_date"], errors="coerce")

    if getattr(dates.dt, "tz", None) is not None:
        start = start.tz_localize(dates.dt.tz)
        next_month = next_month.tz_localize(dates.dt.tz)

    mask = dates.notna() & (dates >= start) & (dates < next_month)
    current_month = hired_people.loc[mask].copy()
    current_month["_hire_date"] = dates.loc[mask]

    sort_columns = [
        column
        for column in ["_hire_date", "job_title", "name"]
        if column in current_month.columns
    ]
    if sort_columns:
        current_month = current_month.sort_values(
            sort_columns,
            na_position="last",
        )

    rows: list[dict[str, Any]] = []
    for _, row in current_month.iterrows():
        hire_date = row["_hire_date"]
        rows.append(
            {
                "job_title": _clean_value(row.get("job_title")),
                "name": _clean_value(row.get("name")),
                "location": _clean_value(row.get("location")),
                "hire_date": (
                    pd.Timestamp(hire_date).strftime("%Y-%m-%d")
                    if not pd.isna(hire_date)
                    else "--"
                ),
            }
        )

    return rows


def count_hires_current_month(
    hired_people: pd.DataFrame,
    reference: datetime,
) -> int:
    return len(get_hires_current_month(hired_people, reference))


def get_peak_hiring_month(
    hires_by_month_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    populated = [
        row for row in hires_by_month_rows if int(row.get("total", 0)) > 0
    ]

    if not populated:
        return {"month": "--", "total": 0}

    peak = max(populated, key=lambda row: int(row["total"]))
    return {
        "month": str(peak.get("month_short") or peak.get("month") or "--"),
        "total": int(peak["total"]),
    }


def get_roles_opened_current_month(
    requisitions_df: pd.DataFrame,
    reference: datetime,
) -> list[dict[str, Any]]:
    """Return currently open requisitions created in the reference month.

    The input already contains only Open Commercial requisitions. We reuse the
    same consolidation applied to the main report so the monthly KPI and its
    dropdown cannot disagree with the open-requisition appendix.
    """
    if requisitions_df.empty or "sent_date" not in requisitions_df.columns:
        return []

    requisitions = prepare_requisitions(requisitions_df)
    if requisitions.empty:
        return []

    start, next_month = _month_bounds(reference)
    start_utc = (
        start.tz_localize("UTC")
        if start.tzinfo is None
        else start.tz_convert("UTC")
    )
    next_month_utc = (
        next_month.tz_localize("UTC")
        if next_month.tzinfo is None
        else next_month.tz_convert("UTC")
    )

    data = requisitions.copy()
    data["_opened_at"] = data["sent_date"].apply(_to_timestamp)
    data = data[
        data["_opened_at"].notna()
        & data["_opened_at"].ge(start_utc)
        & data["_opened_at"].lt(next_month_utc)
    ].copy()

    sort_columns = [
        column
        for column in ["_opened_at", "title", "job_eid", "requisition_id"]
        if column in data.columns
    ]
    if sort_columns:
        data = data.sort_values(sort_columns, na_position="last")

    rows: list[dict[str, Any]] = []
    for _, row in data.iterrows():
        display_id = _clean_value(row.get("job_eid"), "")
        if not display_id:
            display_id = _clean_value(row.get("requisition_id"))

        location = _clean_value(row.get("location"), "")
        if not location:
            location_parts = [
                _clean_value(row.get("location_city"), ""),
                _clean_value(row.get("location_country"), ""),
            ]
            location = ", ".join(part for part in location_parts if part) or "--"

        rows.append(
            {
                "requisition_id": display_id,
                "title": _clean_value(row.get("title")),
                "location": location,
                "opened_date": row["_opened_at"].strftime("%Y-%m-%d"),
            }
        )

    return rows


def count_roles_opened_current_month(
    requisitions_df: pd.DataFrame,
    reference: datetime,
) -> int:
    return len(get_roles_opened_current_month(requisitions_df, reference))


def build_ranked_dimension_with_other(
    structure: pd.DataFrame | None,
    column_name: str,
    label_key: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if structure is None or structure.empty or column_name not in structure.columns:
        return []

    data = structure.copy()
    data[column_name] = (
        data[column_name]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
    )
    data["headcount"] = pd.to_numeric(data["headcount"], errors="coerce").fillna(0).astype(int)

    counts = (
        data.groupby(column_name, as_index=False)["headcount"]
        .sum()
        .sort_values(["headcount", column_name], ascending=[False, True])
        .reset_index(drop=True)
    )

    total_headcount = int(counts["headcount"].sum())
    visible = counts
    other_items: list[dict[str, Any]] = []

    if limit > 1 and len(counts) > limit:
        visible = counts.head(limit - 1).copy()
        hidden = counts.iloc[limit - 1 :].copy()
        other_items = [
            {
                "label": str(row[column_name]),
                "total": int(row["headcount"]),
            }
            for _, row in hidden.iterrows()
        ]
        visible = pd.concat(
            [
                visible,
                pd.DataFrame(
                    [{column_name: "Other", "headcount": int(hidden["headcount"].sum())}]
                ),
            ],
            ignore_index=True,
        )

    maximum = int(visible["headcount"].max()) if not visible.empty else 0
    rows: list[dict[str, Any]] = []

    for _, row in visible.iterrows():
        label = str(row[column_name])
        total = int(row["headcount"])
        rows.append(
            {
                label_key: label,
                "total": total,
                "share": round(total / total_headcount * 100, 1) if total_headcount else 0,
                "width": round(total / maximum * 100, 2) if maximum else 0,
                "other_items": other_items if label == "Other" else [],
            }
        )

    return rows


def build_team_footprint_rows(
    structure: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    if structure is None or structure.empty:
        return []

    required = {"team", "location", "role", "headcount"}
    if not required.issubset(structure.columns):
        return []

    data = structure.copy()
    for column in ["team", "location", "role"]:
        data[column] = (
            data[column]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
            .replace("", "Not specified")
        )
    data["headcount"] = pd.to_numeric(data["headcount"], errors="coerce").fillna(0).astype(int)
    data = data[data["headcount"] > 0]

    rows: list[dict[str, Any]] = []
    for team, group in data.groupby("team", sort=False):
        site_counts = group.groupby("location")["headcount"].sum().sort_values(ascending=False)
        role_counts = group.groupby("role")["headcount"].sum().sort_values(ascending=False)
        rows.append(
            {
                "team": str(team),
                "headcount": int(group["headcount"].sum()),
                "site_count": int(group["location"].nunique()),
                "largest_site": str(site_counts.index[0]) if not site_counts.empty else "--",
                "largest_site_headcount": int(site_counts.iloc[0]) if not site_counts.empty else 0,
                "top_role": str(role_counts.index[0]) if not role_counts.empty else "--",
                "top_role_headcount": int(role_counts.iloc[0]) if not role_counts.empty else 0,
            }
        )

    return sorted(rows, key=lambda row: (-row["headcount"], row["team"].casefold()))


def build_compact_context(
    *,
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
    hibob_structure_df: pd.DataFrame | None,
    reference: datetime | None = None,
    monthly_role_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reference = reference or datetime.now()
    context = build_report_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
    )

    current_month_role_rows = (
        monthly_role_rows
        if monthly_role_rows is not None
        else get_roles_opened_current_month(requisitions_df, reference)
    )
    current_month_hire_rows = get_hires_current_month(
        hired_people_df,
        reference,
    )
    hires_by_month_rows = build_hires_by_month_rows(
        hired_people_df,
        through_month=reference.month,
    )

    context.update(
        {
            "current_year": reference.year,
            "current_month_name": reference.strftime("%B"),
            "current_month_hires": len(current_month_hire_rows),
            "current_month_hire_rows": current_month_hire_rows,
            "hires_by_month_rows": hires_by_month_rows,
            "peak_hiring_month": get_peak_hiring_month(hires_by_month_rows),
            "current_month_new_roles": len(current_month_role_rows),
            "current_month_role_rows": current_month_role_rows,
            "hibob_team_rows_compact": build_ranked_dimension_with_other(
                hibob_structure_df, "team", "team"
            ),
            "hibob_site_rows_compact": build_ranked_dimension_with_other(
                hibob_structure_df, "location", "site"
            ),
            "hibob_role_rows_compact": build_ranked_dimension_with_other(
                hibob_structure_df, "role", "role"
            ),
            "hibob_team_footprint_rows": build_team_footprint_rows(hibob_structure_df),
        }
    )
    return context


def generate_report(
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
    hibob_structure_df: pd.DataFrame | None = None,
    reference: datetime | None = None,
) -> Path:
    reference = reference or datetime.now()
    current_month_role_rows = get_roles_opened_current_month(
        requisitions_df,
        reference,
    )
    context = build_compact_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
        reference=reference,
        monthly_role_rows=current_month_role_rows,
    )

    environment = Environment(
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=True,
        )
    )
    template = environment.from_string(REPORT_TEMPLATE)
    html = template.render(**context)

    output_directory = BASE_DIR / "output"
    output_directory.mkdir(parents=True, exist_ok=True)
    safe_area = area.strip().lower().replace(" ", "_")
    generated_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = output_directory / f"{safe_area}_ta_report_{generated_timestamp}.html"
    output_file.write_text(html, encoding="utf-8")
    return output_file

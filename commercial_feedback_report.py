from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from jinja2 import Environment, select_autoescape

from generate_report import build_report_context
from update_requisitions import (
    JOBVITE_URL,
    PAGE_SIZE,
    get_custom_field,
    get_required_env,
)


BASE_DIR = Path(__file__).resolve().parent
REPORT_TEMPLATE = (
    BASE_DIR / "templates" / "commercial_executive_report_compact.html"
).read_text(encoding="utf-8")

ALL_JOB_STATUSES = [
    "Open",
    "Closed",
    "Filled",
    "On Hold",
    "Awaiting Approval",
    "Approved",
    "Rejected",
    "Retracted",
    "Draft",
]


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


def count_hires_current_month(
    hired_people: pd.DataFrame,
    reference: datetime,
) -> int:
    if hired_people.empty or "app_hire_date" not in hired_people.columns:
        return 0

    start, next_month = _month_bounds(reference)
    dates = pd.to_datetime(hired_people["app_hire_date"], errors="coerce")

    if getattr(dates.dt, "tz", None) is not None:
        start = start.tz_localize(dates.dt.tz)
        next_month = next_month.tz_localize(dates.dt.tz)

    return int(((dates >= start) & (dates < next_month)).sum())


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


def _is_commercial_requisition(requisition: dict[str, Any], area: str) -> bool:
    return (
        get_custom_field(requisition, "business_unit").strip().casefold()
        == area.strip().casefold()
    )


def _is_primary_reporting_requisition(requisition: dict[str, Any]) -> bool:
    excluded = get_custom_field(
        requisition,
        "exclude_from_live_and_ytd",
    ).strip().casefold()
    return excluded not in {"yes", "true", "1", "y"}


def count_roles_opened_current_month(
    area: str,
    reference: datetime | None = None,
) -> int:
    """Count requisitions created this month, including roles no longer open.

    Jobvite's GET Job response exposes `sentDate` as the requisition creation
    timestamp. We request every requisition status because the KPI is about
    roles opened during the month, not only roles that remain open today.
    """
    reference = reference or datetime.now(timezone.utc)
    start, next_month = _month_bounds(reference)
    start_utc = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    next_month_utc = (
        next_month.tz_localize("UTC")
        if next_month.tzinfo is None
        else next_month.tz_convert("UTC")
    )

    api_key = get_required_env("JOBVITE_API_KEY")
    api_secret = get_required_env("JOBVITE_API_SECRET")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "x-jvi-api": api_key,
        "x-jvi-sc": api_secret,
    }

    start_index = 1
    requisition_ids: set[str] = set()
    previous_page_min_date: pd.Timestamp | None = None
    descending_by_creation = True

    while True:
        params: list[tuple[str, str | int]] = [
            ("start", start_index),
            ("count", PAGE_SIZE),
            ("sortBy", "listCreateDate"),
        ]
        params.extend(("jobStatus", status) for status in ALL_JOB_STATUSES)

        response = requests.get(
            JOBVITE_URL,
            headers=headers,
            params=params,
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()

        api_status = payload.get("status") or {}
        if str(api_status.get("code")) != "200":
            raise RuntimeError(
                "Jobvite returned an API error while calculating current-month roles: "
                f"{api_status.get('messages')}"
            )

        requisitions = payload.get("requisitions") or []
        if not isinstance(requisitions, list):
            raise TypeError("The requisitions property is not a list.")

        page_dates = [
            timestamp
            for timestamp in (_to_timestamp(row.get("sentDate")) for row in requisitions)
            if timestamp is not None
        ]

        if page_dates:
            page_max = max(page_dates)
            page_min = min(page_dates)
            if previous_page_min_date is not None and page_max > previous_page_min_date:
                descending_by_creation = False
            previous_page_min_date = page_min

        for requisition in requisitions:
            created_at = _to_timestamp(requisition.get("sentDate"))
            if created_at is None:
                continue
            if created_at < start_utc or created_at >= next_month_utc:
                continue
            if not _is_commercial_requisition(requisition, area):
                continue
            if not _is_primary_reporting_requisition(requisition):
                continue

            identity = str(
                requisition.get("requisitionId")
                or requisition.get("eId")
                or ""
            ).strip()
            if identity:
                requisition_ids.add(identity)

        if len(requisitions) < PAGE_SIZE:
            break

        if descending_by_creation and page_dates and min(page_dates) < start_utc:
            break

        start_index += PAGE_SIZE

    return len(requisition_ids)


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
    monthly_roles_override: int | None = None,
) -> dict[str, Any]:
    reference = reference or datetime.now()
    context = build_report_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
    )

    context.update(
        {
            "current_month_name": reference.strftime("%B"),
            "current_month_hires": count_hires_current_month(hired_people_df, reference),
            "peak_hiring_month": get_peak_hiring_month(context["hires_by_month_rows"]),
            "current_month_new_roles": monthly_roles_override,
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
) -> Path:
    current_month_new_roles = count_roles_opened_current_month(area)
    context = build_compact_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
        monthly_roles_override=current_month_new_roles,
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

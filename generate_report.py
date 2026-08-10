from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, select_autoescape

from hibob_analytics import build_hibob_analytics_context


BASE_DIR = Path(__file__).resolve().parent
LOW_PIPELINE_THRESHOLD = 2
EXCLUDED_ACTIVE_CANDIDATE_STAGES = {
    "candidate withdrew",
    "new",
    "resume screen",
    "info requested left message",
    "sourcing submitted to manager",
}


def load_logo_data_uri() -> str:
    """
    Load logo.png and convert it into an embedded Base64 data URI.

    Embedding the image allows the generated HTML file to work
    independently when it is downloaded, stored in SharePoint,
    or sent as an email attachment.
    """
    logo_path = BASE_DIR / "logo.png"

    if not logo_path.exists():
        print(f"Warning: logo file was not found: {logo_path}")
        return ""

    try:
        logo_bytes = logo_path.read_bytes()
    except OSError as error:
        print(f"Warning: could not read logo file: {error}")
        return ""

    encoded_logo = base64.b64encode(
        logo_bytes
    ).decode("ascii")

    return f"data:image/png;base64,{encoded_logo}"


REPORT_TEMPLATE = (
    BASE_DIR / "templates" / "commercial_executive_report.html"
).read_text(encoding="utf-8")


def clean_value(value: Any, default: str = "--") -> str:
    if value is None or pd.isna(value):
        return default

    cleaned_value = str(value).strip()

    return cleaned_value or default


def get_first_available_value(
    row: pd.Series,
    column_names: list[str],
    default: str = "--",
) -> str:
    for column_name in column_names:
        if column_name not in row.index:
            continue

        value = clean_value(row[column_name], "")

        if value:
            return value

    return default


def get_location_column(
    requisitions_df: pd.DataFrame,
) -> str | None:
    possible_location_columns = [
        "location",
        "locations",
        "job_location",
        "job_location_country",
        "country",
        "job_country",
    ]

    for column_name in possible_location_columns:
        if column_name in requisitions_df.columns:
            return column_name

    return None


def is_yes_value(value: Any) -> bool:
    normalized_value = clean_value(value, "").casefold()

    return normalized_value in {
        "yes",
        "true",
        "1",
        "y",
    }


def consolidate_requisitions(
    requisitions_df: pd.DataFrame,
) -> pd.DataFrame:
    if requisitions_df.empty:
        return requisitions_df.copy()

    requisitions = requisitions_df.copy()

    if "exclude_from_live_and_ytd" not in requisitions.columns:
        return requisitions

    location_column = get_location_column(requisitions)

    requisitions["_is_additional_posting"] = requisitions["exclude_from_live_and_ytd"].apply(is_yes_value)

    grouping_columns = [
        column_name
        for column_name in [
            "title",
            "hiring_manager_user_name",
            "reason",
            "working_type",
        ]
        if column_name in requisitions.columns
    ]

    if not grouping_columns:
        return requisitions[
            ~requisitions["_is_additional_posting"]
        ].drop(
            columns=["_is_additional_posting"]
        ).reset_index(drop=True)

    grouping_key_columns = []

    for column_name in grouping_columns:
        key_column = f"_{column_name}_group_key"

        requisitions[key_column] = requisitions[column_name].fillna("").astype(str).str.strip().str.casefold()

        grouping_key_columns.append(key_column)

    consolidated_rows = []

    grouped_requisitions = requisitions.groupby(
        grouping_key_columns,
        dropna=False,
        sort=False,
    )

    for _, group in grouped_requisitions:
        primary_rows = group[~group["_is_additional_posting"]].copy()

        if primary_rows.empty:
            consolidated_rows.append(group.iloc[0].copy())
            continue

        if location_column is not None and len(primary_rows) == 1:
            locations = group[location_column].dropna().astype(str).str.strip()
            locations = locations[locations.ne("")].drop_duplicates().tolist()

            if locations:
                primary_rows.loc[:, location_column] = ", ".join(locations)

        for _, primary_row in primary_rows.iterrows():
            consolidated_rows.append(primary_row.copy())

    consolidated = pd.DataFrame(consolidated_rows)

    helper_columns = [
        column_name
        for column_name in consolidated.columns
        if column_name.startswith("_")
    ]

    consolidated = consolidated.drop(
        columns=helper_columns,
        errors="ignore",
    )

    if "requisition_id" in consolidated.columns:
        consolidated = consolidated.drop_duplicates(
            subset=["requisition_id"],
            keep="first",
        )

    return consolidated.reset_index(drop=True)


def prepare_requisitions(
    requisitions_df: pd.DataFrame,
) -> pd.DataFrame:
    if requisitions_df.empty:
        return requisitions_df.copy()

    return consolidate_requisitions(requisitions_df)


def prepare_applications(
    applications_df: pd.DataFrame,
) -> pd.DataFrame:
    if applications_df.empty:
        return applications_df.copy()

    applications = applications_df.copy()

    if "app_workflow_state_name" in applications.columns:
        workflow_states = applications["app_workflow_state_name"].fillna("").astype(str).str.strip().str.casefold()

        normalized_workflow_states = (
            workflow_states
            .str.replace(r"[^a-z0-9]+", " ", regex=True)
            .str.strip()
        )

        applications = applications[
            ~workflow_states.str.contains("reject", regex=False)
            & ~workflow_states.str.contains("withdraw", regex=False)
            & ~normalized_workflow_states.isin(
                EXCLUDED_ACTIVE_CANDIDATE_STAGES
            )
        ].copy()

    duplicate_columns = [
        column_name
        for column_name in [
            "app_full_name",
            "job_title",
            "app_workflow_state_name",
        ]
        if column_name in applications.columns
    ]

    if duplicate_columns:
        applications = applications.drop_duplicates(
            subset=duplicate_columns,
            keep="first",
        )

    return applications.reset_index(drop=True)


def build_stage_rows(
    applications: pd.DataFrame,
    limit: int = 7,
) -> list[dict[str, Any]]:
    if applications.empty:
        return []

    if "app_workflow_state_name" not in applications.columns:
        return []

    stage_counts = applications["app_workflow_state_name"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("stage").reset_index(name="total")

    if limit > 1 and len(stage_counts) > limit:
        visible_counts = stage_counts.head(limit - 1).copy()
        other_total = int(stage_counts.iloc[limit - 1 :]["total"].sum())
        stage_counts = pd.concat(
            [
                visible_counts,
                pd.DataFrame(
                    [{"stage": "Other stages", "total": other_total}]
                ),
            ],
            ignore_index=True,
        )

    maximum_stage_total = int(stage_counts["total"].max())

    stage_rows = []

    for _, row in stage_counts.iterrows():
        total = int(row["total"])

        width = round(
            total / maximum_stage_total * 100,
            2,
        ) if maximum_stage_total else 0

        stage_rows.append(
            {
                "stage": clean_value(
                    row["stage"],
                    "Not specified",
                ),
                "total": total,
                "width": width,
            }
        )

    return stage_rows


def build_pipeline_by_title(
    requisitions: pd.DataFrame,
    applications: pd.DataFrame,
) -> list[dict[str, Any]]:
    if requisitions.empty or "title" not in requisitions.columns:
        return []

    requisition_titles = (
        requisitions["title"]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
    )
    open_roles_by_title = pd.DataFrame(
        {
            "job_title": requisition_titles,
            "_job_title_key": requisition_titles.str.casefold(),
        }
    )
    open_roles_by_title = (
        open_roles_by_title.groupby(
            "_job_title_key",
            as_index=False,
            sort=False,
        )
        .agg(
            job_title=("job_title", "first"),
            open_positions=("job_title", "size"),
        )
    )

    if applications.empty or "job_title" not in applications.columns:
        candidates_by_title = pd.DataFrame(
            columns=[
                "_job_title_key",
                "active_candidates",
            ]
        )
    else:
        candidate_titles = (
            applications["job_title"]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
            .replace("", "Not specified")
        )
        candidates_by_title = pd.DataFrame(
            {"_job_title_key": candidate_titles.str.casefold()}
        )
        candidates_by_title = (
            candidates_by_title.value_counts("_job_title_key")
            .rename("active_candidates")
            .reset_index()
        )

    pipeline_by_title = open_roles_by_title.merge(
        candidates_by_title,
        on="_job_title_key",
        how="left",
    )
    pipeline_by_title = pipeline_by_title.drop(
        columns=["_job_title_key"]
    )

    pipeline_by_title["active_candidates"] = (
        pd.to_numeric(
            pipeline_by_title["active_candidates"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    pipeline_by_title["candidates_per_opening"] = (
        pipeline_by_title["active_candidates"]
        / pipeline_by_title["open_positions"]
    ).round(2)

    maximum_candidate_total = int(
        pipeline_by_title["active_candidates"].max()
    )

    def calculate_pipeline_status(
        candidates_per_opening: float,
    ) -> str:
        if candidates_per_opening == 0:
            return "No active pipeline"

        if candidates_per_opening < LOW_PIPELINE_THRESHOLD:
            return "Needs attention"

        return "Active pipeline"

    pipeline_by_title["status"] = pipeline_by_title["candidates_per_opening"].apply(calculate_pipeline_status)

    pipeline_by_title = pipeline_by_title.sort_values(
        by=[
            "active_candidates",
            "job_title",
        ],
        ascending=[
            False,
            True,
        ],
    )

    pipeline_rows = []

    for _, row in pipeline_by_title.iterrows():
        active_candidates = int(row["active_candidates"])
        candidates_per_opening = float(row["candidates_per_opening"])

        if active_candidates == 0:
            chart_class = "chart-empty"
        elif candidates_per_opening < LOW_PIPELINE_THRESHOLD:
            chart_class = "chart-warning"
        else:
            chart_class = "chart-active"

        chart_width = round(
            active_candidates / maximum_candidate_total * 100,
            2,
        ) if maximum_candidate_total else 0

        pipeline_rows.append(
            {
                "job_title": clean_value(row["job_title"]),
                "open_positions": int(row["open_positions"]),
                "active_candidates": active_candidates,
                "candidates_per_opening": candidates_per_opening,
                "status": clean_value(row["status"]),
                "chart_class": chart_class,
                "chart_width": chart_width,
            }
        )

    return pipeline_rows


def build_source_rows(
    applications: pd.DataFrame,
) -> tuple[list[dict[str, Any]], str, float]:
    if applications.empty or "app_sourcetype" not in applications.columns:
        return [], "--", 0

    source_counts = applications["app_sourcetype"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("source").reset_index(name="total")

    total_candidates = int(source_counts["total"].sum())
    maximum_source_total = int(source_counts["total"].max())

    source_rows = []

    for _, row in source_counts.iterrows():
        total = int(row["total"])

        source_rows.append(
            {
                "source": clean_value(
                    row["source"],
                    "Not specified",
                ),
                "total": total,
                "share": round(
                    total / total_candidates * 100,
                    1,
                ) if total_candidates else 0,
                "width": round(
                    total / maximum_source_total * 100,
                    2,
                ) if maximum_source_total else 0,
            }
        )

    top_source = clean_value(
        source_counts.iloc[0]["source"],
        "Not specified",
    )

    top_source_total = int(
        source_counts.iloc[0]["total"]
    )

    top_source_share = round(
        top_source_total / total_candidates * 100,
        1,
    ) if total_candidates else 0

    return source_rows, top_source, top_source_share



def build_count_rows(
    dataframe: pd.DataFrame,
    column_name: str,
    label_key: str,
    total_key: str = "total",
    limit: int = 10,
) -> list[dict[str, Any]]:
    if dataframe.empty or column_name not in dataframe.columns:
        return []

    counts = (
        dataframe[column_name]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
        .value_counts()
        .head(limit)
        .rename_axis(label_key)
        .reset_index(name=total_key)
    )

    maximum_total = int(counts[total_key].max()) if not counts.empty else 0

    rows = []

    for _, row in counts.iterrows():
        total = int(row[total_key])

        rows.append(
            {
                label_key: clean_value(row[label_key], "Not specified"),
                total_key: total,
                "width": round(total / maximum_total * 100, 2) if maximum_total else 0,
            }
        )

    return rows


def build_distribution_segments(
    dataframe: pd.DataFrame,
    column_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Build a compact, lossless part-to-whole distribution."""
    if dataframe.empty or column_name not in dataframe.columns:
        return []

    counts = (
        dataframe[column_name]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
        .value_counts()
        .rename_axis("label")
        .reset_index(name="total")
    )

    if limit > 1 and len(counts) > limit:
        visible_counts = counts.head(limit - 1).copy()
        other_total = int(counts.iloc[limit - 1 :]["total"].sum())
        counts = pd.concat(
            [
                visible_counts,
                pd.DataFrame(
                    [{"label": "Other", "total": other_total}]
                ),
            ],
            ignore_index=True,
        )

    total_count = int(counts["total"].sum())

    return [
        {
            "label": clean_value(row.label, "Not specified"),
            "total": int(row.total),
            "share": round(int(row.total) / total_count * 100, 1)
            if total_count
            else 0,
        }
        for row in counts.itertuples(index=False)
    ]


def build_geography_comparison_rows(
    active_role_country_rows: list[dict[str, Any]],
    hire_country_rows: list[dict[str, Any]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Align role and hire geographies without implying funnel conversion."""
    geography: dict[str, dict[str, Any]] = {}

    def add_rows(
        rows: list[dict[str, Any]],
        metric_key: str,
    ) -> None:
        for row in rows:
            label = clean_value(row.get("country"), "Not specified")
            normalized_label = label.casefold()
            entry = geography.setdefault(
                normalized_label,
                {
                    "country": label,
                    "open_roles": 0,
                    "hires": 0,
                },
            )
            entry[metric_key] += int(row.get("total", 0))

    add_rows(active_role_country_rows, "open_roles")
    add_rows(hire_country_rows, "hires")

    rows = sorted(
        geography.values(),
        key=lambda row: (
            -max(row["open_roles"], row["hires"]),
            -row["open_roles"],
            -row["hires"],
            row["country"].casefold(),
        ),
    )

    if limit > 1 and len(rows) > limit:
        visible_rows = rows[: limit - 1]
        remaining_rows = rows[limit - 1 :]
        rows = [
            *visible_rows,
            {
                "country": "Other",
                "open_roles": sum(
                    row["open_roles"] for row in remaining_rows
                ),
                "hires": sum(row["hires"] for row in remaining_rows),
            },
        ]

    maximum_total = max(
        (
            max(row["open_roles"], row["hires"])
            for row in rows
        ),
        default=0,
    )

    for row in rows:
        row["open_width"] = round(
            row["open_roles"] / maximum_total * 100,
            2,
        ) if maximum_total else 0
        row["hire_width"] = round(
            row["hires"] / maximum_total * 100,
            2,
        ) if maximum_total else 0

    return rows


def build_executive_insights(
    *,
    total_open_roles: int,
    total_active_candidates: int,
    new_roles: int,
    backfill_roles: int,
    hires_by_month_rows: list[dict[str, Any]],
    pipeline_by_title: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Create concise, descriptive insights for executive readers."""
    if total_open_roles:
        coverage = total_active_candidates / total_open_roles
        coverage_value = f"{coverage:.1f}x"
        coverage_detail = (
            f"{total_active_candidates} filtered active candidates across "
            f"{total_open_roles} open requisitions."
        )
    else:
        coverage_value = "--"
        coverage_detail = "There are no open requisitions in scope."

    uncovered_roles = sum(
        int(row["open_positions"])
        for row in pipeline_by_title
        if int(row["active_candidates"]) == 0
    )

    if total_open_roles:
        uncovered_detail = (
            f"{uncovered_roles} of {total_open_roles} open requisitions sit "
            "in job titles with no filtered active candidates."
        )
    else:
        uncovered_detail = "There is no current demand to assess."

    completed_months = [
        row for row in hires_by_month_rows if int(row["total"]) > 0
    ]

    if completed_months:
        peak_month = max(
            completed_months,
            key=lambda row: int(row["total"]),
        )
        peak_value = str(peak_month["month_short"])
        peak_detail = (
            f"{peak_month['month']} recorded the highest YTD hiring volume "
            f"with {int(peak_month['total'])} hires."
        )
    else:
        peak_value = "0"
        peak_detail = "No hires have been recorded in the current year."

    classified_roles = new_roles + backfill_roles

    if total_open_roles:
        new_role_share = round(new_roles / total_open_roles * 100)
        mix_value = f"{new_role_share}%"
        other_roles = total_open_roles - classified_roles
        mix_detail = (
            f"{new_roles} new, {backfill_roles} backfill and "
            f"{max(other_roles, 0)} other or unclassified requisitions."
        )
    else:
        mix_value = "--"
        mix_detail = "There are no open requisitions to classify."

    return [
        {
            "label": "Pipeline coverage",
            "value": coverage_value,
            "headline": "Active candidates per open role",
            "detail": coverage_detail,
            "tone": "accent",
        },
        {
            "label": "Coverage watch",
            "value": str(uncovered_roles),
            "headline": "Open roles without active pipeline",
            "detail": uncovered_detail,
            "tone": "attention" if uncovered_roles else "positive",
        },
        {
            "label": "Hiring momentum",
            "value": peak_value,
            "headline": "Peak hiring month",
            "detail": peak_detail,
            "tone": "neutral",
        },
        {
            "label": "Demand profile",
            "value": mix_value,
            "headline": "Open demand classified as new",
            "detail": mix_detail,
            "tone": "neutral",
        },
    ]


def build_hires_by_month_rows(
    hired_people: pd.DataFrame,
    through_month: int | None = None,
) -> list[dict[str, Any]]:
    month_names = [
        ("January", "Jan"),
        ("February", "Feb"),
        ("March", "Mar"),
        ("April", "Apr"),
        ("May", "May"),
        ("June", "Jun"),
        ("July", "Jul"),
        ("August", "Aug"),
        ("September", "Sep"),
        ("October", "Oct"),
        ("November", "Nov"),
        ("December", "Dec"),
    ]

    if through_month is None:
        through_month = datetime.now().month

    through_month = max(1, min(int(through_month), 12))
    visible_months = month_names[:through_month]

    if hired_people.empty or "app_hire_date" not in hired_people.columns:
        return [
            {"month": month, "month_short": short, "total": 0, "height": 0}
            for month, short in visible_months
        ]

    hire_dates = pd.to_datetime(
        hired_people["app_hire_date"],
        errors="coerce",
    ).dropna()

    month_counts = hire_dates.dt.month.value_counts().to_dict()
    maximum_total = max(month_counts.values()) if month_counts else 0

    rows = []

    for month_number, (month, short) in enumerate(visible_months, start=1):
        total = int(month_counts.get(month_number, 0))

        rows.append(
            {
                "month": month,
                "month_short": short,
                "total": total,
                "height": round(total / maximum_total * 100, 2) if maximum_total else 0,
            }
        )

    return rows



def build_submitted_to_manager_rows(
    applications: pd.DataFrame,
) -> list[dict[str, Any]]:
    if applications.empty:
        return []

    required_columns = {
        "app_workflow_state_name",
        "job_title",
    }

    if not required_columns.issubset(applications.columns):
        return []

    submitted = applications[
        applications["app_workflow_state_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq("submitted to manager")
    ].copy()

    return build_count_rows(
        submitted,
        column_name="job_title",
        label_key="job_title",
    )


def build_report_context(
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
    hibob_structure_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    report_timestamp = datetime.now()
    requisitions = prepare_requisitions(requisitions_df)
    applications = prepare_applications(applications_df)
    hired_people = hired_people_df.copy()

    location_column = get_location_column(requisitions)

    roles = []

    for _, row in requisitions.iterrows():
        location_columns = [
            column_name
            for column_name in [
                location_column,
                "location",
                "job_location",
                "job_location_country",
                "country",
                "job_country",
            ]
            if column_name
        ]

        roles.append(
            {
                "requisition_id": get_first_available_value(
                    row,
                    [
                        "requisition_id",
                        "job_eid",
                    ],
                ),
                "title": get_first_available_value(
                    row,
                    [
                        "title",
                        "job_title",
                    ],
                ),
                "reason": get_first_available_value(
                    row,
                    ["reason"],
                    "Not specified",
                ),
                "hiring_manager": get_first_available_value(
                    row,
                    [
                        "hiring_manager_user_name",
                        "job_primary_hm_full_name",
                        "hiring_manager",
                    ],
                ),
                "working_type": get_first_available_value(
                    row,
                    ["working_type"],
                ),
                "location": get_first_available_value(
                    row,
                    location_columns,
                ),
            }
        )

    candidates = []

    for _, row in applications.iterrows():
        candidates.append(
            {
                "name": get_first_available_value(
                    row,
                    ["app_full_name"],
                ),
                "job_title": get_first_available_value(
                    row,
                    ["job_title"],
                ),
                "stage": get_first_available_value(
                    row,
                    ["app_workflow_state_name"],
                    "Not specified",
                ),
                "country": get_first_available_value(
                    row,
                    ["app_country"],
                ),
                "source": get_first_available_value(
                    row,
                    ["app_sourcetype"],
                ),
            }
        )

    hires = []

    for _, row in hired_people.iterrows():
        hire_date_value = row.get("app_hire_date")

        if hire_date_value is not None and not pd.isna(hire_date_value):
            hire_date = pd.to_datetime(
                hire_date_value
            ).strftime("%Y-%m-%d")
        else:
            hire_date = "--"

        hires.append(
            {
                "job_title": get_first_available_value(
                    row,
                    ["job_title"],
                ),
                "name": get_first_available_value(
                    row,
                    [
                        "name",
                        "app_full_name",
                    ],
                ),
                "location": get_first_available_value(
                    row,
                    [
                        "location",
                        "app_country",
                    ],
                ),
                "month": get_first_available_value(
                    row,
                    ["month_of_hire"],
                ),
                "hire_date": hire_date,
            }
        )

    stage_rows = build_stage_rows(applications)
    pipeline_by_title = build_pipeline_by_title(
        requisitions,
        applications,
    )

    hires_by_month_rows = build_hires_by_month_rows(
        hired_people,
        through_month=report_timestamp.month,
    )

    active_role_country_rows = build_count_rows(
        requisitions,
        column_name="location_country",
        label_key="country",
        limit=100,
    )

    hire_country_rows = build_count_rows(
        hired_people,
        column_name="location",
        label_key="country",
        limit=100,
    )

    working_type_rows = build_count_rows(
        requisitions,
        column_name="working_type",
        label_key="working_type",
    )

    reason_rows = build_count_rows(
        requisitions,
        column_name="reason",
        label_key="reason",
    )

    geography_rows = build_geography_comparison_rows(
        active_role_country_rows,
        hire_country_rows,
    )

    reason_mix_segments = build_distribution_segments(
        requisitions,
        column_name="reason",
    )

    working_type_mix_segments = build_distribution_segments(
        requisitions,
        column_name="working_type",
    )

    total_open_roles = len(requisitions)
    total_active_candidates = len(applications)
    total_hired = len(hired_people)

    if "reason" in requisitions.columns:
        reasons = requisitions["reason"].fillna("").astype(str).str.strip().str.casefold()
    else:
        reasons = pd.Series(dtype=str)

    new_roles = int(reasons.eq("new").sum())
    backfill_roles = int(reasons.eq("backfill").sum())

    executive_insights = build_executive_insights(
        total_open_roles=total_open_roles,
        total_active_candidates=total_active_candidates,
        new_roles=new_roles,
        backfill_roles=backfill_roles,
        hires_by_month_rows=hires_by_month_rows,
        pipeline_by_title=pipeline_by_title,
    )

    hibob_context = build_hibob_analytics_context(
        hibob_structure_df
    )

    return {
        "area": clean_value(area, "Unknown"),
        "generated_at": report_timestamp.strftime("%Y-%m-%d %H:%M"),
        "current_year": report_timestamp.year,
        "total_open_roles": total_open_roles,
        "total_active_candidates": total_active_candidates,
        "total_hired": total_hired,
        "new_roles": new_roles,
        "backfill_roles": backfill_roles,
        "roles": roles,
        "candidates": candidates,
        "stage_rows": stage_rows,
        "pipeline_by_title": pipeline_by_title,
        "hires": hires,
        "hires_by_month_rows": hires_by_month_rows,
        "active_role_country_rows": active_role_country_rows,
        "hire_country_rows": hire_country_rows,
        "geography_rows": geography_rows,
        "working_type_rows": working_type_rows,
        "reason_rows": reason_rows,
        "reason_mix_segments": reason_mix_segments,
        "working_type_mix_segments": working_type_mix_segments,
        "executive_insights": executive_insights,
        "hire_geography_note": (
            "Open roles use requisition location country. Hires use the "
            "candidate-country field currently exposed by hires_ytd; the "
            "two series show geographic distributions and must not be read "
            "as a location conversion rate."
        ),
        "logo_data_uri": load_logo_data_uri(),
        **hibob_context,
    }


def generate_report(
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
    hibob_structure_df: pd.DataFrame | None = None,
) -> Path:
    context = build_report_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
    )

    environment = Environment(
        autoescape=select_autoescape(
            enabled_extensions=(
                "html",
                "xml",
            ),
            default_for_string=True,
        )
    )

    template = environment.from_string(
        REPORT_TEMPLATE
    )

    html = template.render(
        **context
    )

    output_directory = BASE_DIR / "output"
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_area = area.strip().lower().replace(" ", "_")

    generated_timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    output_file = output_directory / (
        f"{safe_area}_ta_report_{generated_timestamp}.html"
    )

    output_file.write_text(
        html,
        encoding="utf-8",
    )

    return output_file

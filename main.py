from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import zipfile

import pandas as pd
from dotenv import load_dotenv
from psycopg2 import sql

from commercial_feedback_report import generate_report
from commercial_utils import get_hired_people_current_year
from generate_report import EXCLUDED_ACTIVE_CANDIDATE_STAGES
from hibob_analytics import (
    DEFAULT_HIBOB_SCHEMA,
    DEFAULT_HIBOB_TABLE,
    _coalesced_text_expression,
    _get_relation_columns,
    _resolve_business_unit_column,
    get_current_commercial_structure,
)
# from send_report_power_automate import send_html_report
from update_requisitions import (
    DATAFRAME_COLUMNS,
    fetch_all_requisitions,
    get_custom_field,
    get_required_env,
    normalize_requisition,
)
from utils import (
    get_open_job_applications,
    get_postgres_connection,
)


REPORT_AREA = "Commercial"
REPORT_REFERENCE_DATE_ENV = "REPORT_REFERENCE_DATE"
DATA_COPY_ROOT = Path("output")


def get_report_reference_date() -> datetime | None:
    raw_value = os.getenv(REPORT_REFERENCE_DATE_ENV, "").strip()

    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(
            f"{REPORT_REFERENCE_DATE_ENV} must use YYYY-MM-DD format. "
            f"Received: {raw_value!r}"
        ) from error


def get_jobvite_api_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return report requisitions and the filtered raw Jobvite API response."""
    api_key = get_required_env("JOBVITE_API_KEY")
    api_secret = get_required_env("JOBVITE_API_SECRET")

    raw_requisitions = fetch_all_requisitions(
        api_key=api_key,
        api_secret=api_secret,
    )

    commercial_requisitions = [
        requisition
        for requisition in raw_requisitions
        if get_custom_field(
            requisition=requisition,
            field_code="business_unit",
        ).strip().casefold()
        == REPORT_AREA.casefold()
    ]

    report_requisitions_df = pd.DataFrame(
        [
            normalize_requisition(requisition)
            for requisition in commercial_requisitions
        ],
        columns=DATAFRAME_COLUMNS,
    )

    if commercial_requisitions:
        raw_api_df = pd.json_normalize(
            commercial_requisitions,
            sep=".",
        )
        raw_api_df.insert(
            0,
            "_raw_json",
            [
                json.dumps(
                    requisition,
                    ensure_ascii=False,
                    default=str,
                )
                for requisition in commercial_requisitions
            ],
        )
    else:
        raw_api_df = pd.DataFrame()

    return report_requisitions_df, raw_api_df


def get_jobvite_filtered_raw_data(
    job_eids: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return full-column Jobvite rows matching the report scope."""
    normalized_job_eids = list(
        dict.fromkeys(
            str(job_eid).strip()
            for job_eid in job_eids
            if job_eid is not None and str(job_eid).strip()
        )
    )

    if not normalized_job_eids:
        return pd.DataFrame(), pd.DataFrame()

    placeholders = ", ".join(["%s"] * len(normalized_job_eids))

    applications_query = f"""
        SELECT *
        FROM jv_arrise_data_schema.applications
        WHERE job_eid IN ({placeholders})
          AND app_id IS NOT NULL
          AND COALESCE(TRIM(state_name), '') NOT ILIKE '%%reject%%'
          AND COALESCE(TRIM(state_name), '') NOT ILIKE '%%withdraw%%';
    """

    hires_query = """
        SELECT DISTINCT ON (hires.app_id)
            hires.*
        FROM jv_arrise_data_schema.hires_ytd AS hires
        JOIN jv_arrise_data_schema.jobvite_applications AS applications
          ON applications.application_eid = hires.app_id
        WHERE hires.hire_date IS NOT NULL
          AND hires.app_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(
                  COALESCE(
                      applications.raw_payload
                          #> '{application,job,customField}',
                      '[]'::jsonb
                  )
              ) AS custom_field
              WHERE custom_field ->> 'fieldCode' = 'business_unit'
                AND LOWER(TRIM(custom_field ->> 'value')) = %s
          )
        ORDER BY
            hires.app_id,
            hires.hire_date DESC;
    """

    connection = None

    try:
        connection = get_postgres_connection()

        applications_raw = pd.read_sql_query(
            sql=applications_query,
            con=connection,
            params=tuple(normalized_job_eids),
        )

        hires_raw = pd.read_sql_query(
            sql=hires_query,
            con=connection,
            params=(REPORT_AREA.casefold(),),
        )
    finally:
        if connection is not None:
            connection.close()

    if "state_name" in applications_raw.columns:
        workflow_states = (
            applications_raw["state_name"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
        )
        normalized_states = (
            workflow_states
            .str.replace(r"[^a-z0-9]+", " ", regex=True)
            .str.strip()
        )

        applications_raw = applications_raw[
            ~workflow_states.str.contains("reject", regex=False)
            & ~workflow_states.str.contains("withdraw", regex=False)
            & ~normalized_states.isin(EXCLUDED_ACTIVE_CANDIDATE_STAGES)
        ].copy()

    duplicate_columns = [
        column
        for column in ["full_name", "title", "state_name"]
        if column in applications_raw.columns
    ]

    if duplicate_columns:
        applications_raw = applications_raw.drop_duplicates(
            subset=duplicate_columns,
            keep="first",
        )

    return (
        applications_raw.reset_index(drop=True),
        hires_raw.reset_index(drop=True),
    )


def get_hibob_raw_commercial_data() -> pd.DataFrame:
    """Return full-column active Commercial rows from the HiBob source table."""
    schema = os.getenv(
        "HIBOB_POSTGRES_SCHEMA",
        DEFAULT_HIBOB_SCHEMA,
    ).strip()
    table = os.getenv(
        "HIBOB_POSTGRES_TABLE",
        DEFAULT_HIBOB_TABLE,
    ).strip()

    connection = None

    try:
        connection = get_postgres_connection()

        columns = _get_relation_columns(
            connection=connection,
            schema=schema,
            table=table,
        )

        business_unit_column = _resolve_business_unit_column(
            connection=connection,
            schema=schema,
            table=table,
            columns=columns,
            business_unit=REPORT_AREA,
        )

        status_expression = _coalesced_text_expression(
            columns=columns,
            preferred_column="hr_internal_status",
            fallback_column="raw_internal_status",
            default="",
        )

        query = sql.SQL(
            """
            SELECT *
            FROM {schema}.{table}
            WHERE LOWER(BTRIM({business_unit_column})) = %s
              AND LOWER({status}) = 'active'
              AND hibob_root_id IS NOT NULL
            ORDER BY hibob_root_id;
            """
        ).format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            business_unit_column=sql.Identifier(
                business_unit_column
            ),
            status=status_expression,
        )

        return pd.read_sql_query(
            sql=query.as_string(connection),
            con=connection,
            params=(REPORT_AREA.casefold(),),
        )
    finally:
        if connection is not None:
            connection.close()


def export_report_data_copy(
    *,
    jobvite_api_df: pd.DataFrame,
    jobvite_applications_df: pd.DataFrame,
    jobvite_hires_df: pd.DataFrame,
    hibob_raw_df: pd.DataFrame,
) -> Path:
    """Create one ZIP containing the three source groups used by the report."""
    generated_at = datetime.now()
    DATA_COPY_ROOT.mkdir(parents=True, exist_ok=True)

    output_file = (
        DATA_COPY_ROOT
        / f"commercial_report_source_data_{generated_at:%Y-%m-%d_%H-%M-%S}.zip"
    )

    print()
    print("Creating source data copy...")
    print("----------------------------")
    print(
        "Jobvite API filter: status=Open; "
        "business_unit=Commercial."
    )
    print(
        "Jobvite applications filter: open Commercial job_eids; "
        "app_id present; rejected/withdrawn and excluded early stages removed; "
        "same duplicate rule as the report."
    )
    print(
        "Jobvite hires filter: business_unit=Commercial; hire_date/app_id present; "
        "latest row per app_id."
    )
    print(
        "HiBob filter: business_unit=Commercial; internal_status=active; "
        "hibob_root_id present."
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)

        api_dir = root / "01_jobvite_api"
        jobvite_dir = root / "02_jobvite_filtered"
        hibob_dir = root / "03_hibob"

        api_dir.mkdir()
        jobvite_dir.mkdir()
        hibob_dir.mkdir()

        jobvite_api_df.to_csv(
            api_dir / "jobvite_api_open_commercial.csv",
            index=False,
            encoding="utf-8-sig",
        )
        jobvite_applications_df.to_csv(
            jobvite_dir / "jobvite_applications_report_scope.csv",
            index=False,
            encoding="utf-8-sig",
        )
        jobvite_hires_df.to_csv(
            jobvite_dir / "jobvite_hires_ytd_commercial.csv",
            index=False,
            encoding="utf-8-sig",
        )
        hibob_raw_df.to_csv(
            hibob_dir / "hibob_commercial_active.csv",
            index=False,
            encoding="utf-8-sig",
        )

        with zipfile.ZipFile(
            output_file,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for file_path in root.rglob("*"):
                if file_path.is_file():
                    archive.write(
                        file_path,
                        arcname=file_path.relative_to(root),
                    )

    file_size_mb = output_file.stat().st_size / (1024 * 1024)

    print(
        f"  Jobvite API: {len(jobvite_api_df):,} rows"
    )
    print(
        f"  Jobvite applications: "
        f"{len(jobvite_applications_df):,} rows"
    )
    print(
        f"  Jobvite hires: {len(jobvite_hires_df):,} rows"
    )
    print(
        f"  HiBob: {len(hibob_raw_df):,} rows"
    )
    print(
        f"Source data ZIP created: {output_file} "
        f"({file_size_mb:.2f} MB)"
    )
    print()

    return output_file


def main() -> None:
    load_dotenv(override=True)
    report_reference = get_report_reference_date()

    print("Starting report generation... by area:", REPORT_AREA)
    print(
        "Report month:",
        (
            report_reference.strftime("%B %Y")
            if report_reference is not None
            else "current month"
        ),
    )

    requisitions_df, jobvite_api_raw_df = get_jobvite_api_data()

    print(
        "Open requisitions found for Commercial business unit:",
        len(requisitions_df),
    )

    job_eids = (
        requisitions_df["job_eid"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda values: values.ne("")]
        .drop_duplicates()
        .tolist()
    )

    applications_df = get_open_job_applications(job_eids)

    hired_people_df = get_hired_people_current_year(REPORT_AREA)

    hibob_structure_df = get_current_commercial_structure(REPORT_AREA)

    print(
        "HiBob Commercial team/location/role groups found:",
        len(hibob_structure_df),
    )

    report_file = generate_report(
        area=REPORT_AREA,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
        reference=report_reference,
    )

    print("HTML report generated successfully:")
    print(report_file)

    jobvite_applications_raw_df, jobvite_hires_raw_df = (
        get_jobvite_filtered_raw_data(job_eids)
    )
    hibob_raw_df = get_hibob_raw_commercial_data()

    export_report_data_copy(
        jobvite_api_df=jobvite_api_raw_df,
        jobvite_applications_df=jobvite_applications_raw_df,
        jobvite_hires_df=jobvite_hires_raw_df,
        hibob_raw_df=hibob_raw_df,
    )

    # send_html_report(report_file)


if __name__ == "__main__":
    main()

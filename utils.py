from __future__ import annotations

import os
from typing import Sequence

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection
from datetime import datetime
from pathlib import Path

def export_applications_debug_log(
    applications_df: pd.DataFrame,
    requisitions_df: pd.DataFrame,
) -> Path:
    """
    Exporta las aplicaciones recuperadas y verifica si su vacante
    pertenece realmente al conjunto de requisiciones abiertas del reporte.
    """
    output_dir = Path("output") / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"applications_debug_{timestamp}.csv"

    applications = applications_df.copy()
    requisitions = requisitions_df.copy()

    open_job_eids = set(
        requisitions.get("job_eid", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
        .loc[lambda values: values.ne("")]
    )

    open_requisition_ids = set(
        requisitions.get("requisition_id", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
        .loc[lambda values: values.ne("")]
    )

    if "job_eid" in applications.columns:
        applications["job_eid"] = (
            applications["job_eid"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        applications["job_eid_is_open"] = applications[
            "job_eid"
        ].isin(open_job_eids)
    else:
        applications["job_eid_is_open"] = False

    if "requisition_id" in applications.columns:
        applications["requisition_id"] = (
            applications["requisition_id"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        applications["requisition_id_is_open"] = applications[
            "requisition_id"
        ].isin(open_requisition_ids)
    else:
        applications["requisition_id_is_open"] = False

    applications["matched_open_requisition"] = (
        applications["job_eid_is_open"]
        | applications["requisition_id_is_open"]
    )

    applications.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    invalid_count = int(
        (~applications["matched_open_requisition"]).sum()
    )

    print()
    print("Application diagnostic")
    print("----------------------")
    print(f"Applications retrieved: {len(applications)}")
    print(f"Valid open requisitions: {len(requisitions)}")
    print(f"Applications outside open requisitions: {invalid_count}")
    print(f"Debug file: {output_file}")
    print()

    if invalid_count:
        columns_to_show = [
            column
            for column in [
                "app_id",
                "app_full_name",
                "job_title",
                "job_eid",
                "requisition_id",
                "app_workflow_state_name",
            ]
            if column in applications.columns
        ]

        print("Sample applications incorrectly included:")
        print(
            applications.loc[
                ~applications["matched_open_requisition"],
                columns_to_show,
            ].head(30).to_string(index=False)
        )

    return output_file

QUERY_GET_HIRED_PEOPLE = """
WITH hired_people AS (
    SELECT
        app_id,
        job_title,
        full_name,
        candidate_country,
        hire_date,
        ROW_NUMBER() OVER (
            PARTITION BY app_id
            ORDER BY hire_date DESC
        ) AS row_number
    FROM jv_arrise_data_schema.hires_ytd
    WHERE LOWER(TRIM(department)) = LOWER(TRIM(%(department)s))
      AND hire_date IS NOT NULL
      AND app_id IS NOT NULL
)
SELECT
    app_id,
    job_title,
    full_name AS name,
    candidate_country AS location,
    TRIM(TO_CHAR(hire_date, 'Month')) AS month_of_hire,
    hire_date AS app_hire_date
FROM hired_people
WHERE row_number = 1
ORDER BY
    hire_date ASC,
    job_title ASC,
    name ASC;
"""


def get_postgres_connection() -> connection:
    load_dotenv(override=True)

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DBNAME", "arrise_vm_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
        connect_timeout=15,
    )


def normalize_job_titles(
    job_titles: Sequence[str],
) -> list[str]:
    normalized_job_titles = [
        str(title).strip().casefold()
        for title in job_titles
        if title is not None and str(title).strip()
    ]

    return list(dict.fromkeys(normalized_job_titles))


def get_open_job_applications(
    job_eids: Sequence[str],
) -> pd.DataFrame:
    normalized_job_eids = [
        str(job_eid).strip()
        for job_eid in job_eids
        if job_eid is not None and str(job_eid).strip()
    ]

    normalized_job_eids = list(
        dict.fromkeys(normalized_job_eids)
    )

    output_columns = [
        "app_id",
        "job_eid",
        "requisition_id",
        "app_workflow_state_name",
        "app_full_name",
        "app_country",
        "app_sourcetype",
        "job_title",
        "app_hire_date",
    ]

    if not normalized_job_eids:
        print("No valid open job_eids were provided.")
        return pd.DataFrame(columns=output_columns)

    placeholders = ", ".join(
        ["%s"] * len(normalized_job_eids)
    )

    query = f"""
        SELECT DISTINCT
            app_id,
            job_eid,
            requisition_id,
            state_name AS app_workflow_state_name,
            full_name AS app_full_name,
            country AS app_country,
            source_type AS app_sourcetype,
            title AS job_title,
            NULL::date AS app_hire_date
        FROM jv_arrise_data_schema.applications
        WHERE job_eid IN ({placeholders})
          AND app_id IS NOT NULL
          AND COALESCE(TRIM(state_name), '') NOT ILIKE '%%reject%%'
          AND COALESCE(TRIM(state_name), '') NOT ILIKE '%%withdraw%%'
        ORDER BY
            job_title,
            app_full_name,
            app_workflow_state_name;
    """

    connection = None

    try:
        connection = get_postgres_connection()

        return pd.read_sql_query(
            sql=query,
            con=connection,
            params=tuple(normalized_job_eids),
        )

    except Exception as error:
        raise RuntimeError(
            f"Error retrieving applications from PostgreSQL: {error}"
        ) from error

    finally:
        if connection is not None:
            connection.close()


def get_hired_people_current_year(
    department: str,
) -> pd.DataFrame:
    clean_department = department.strip()

    if not clean_department:
        raise ValueError("Department cannot be empty.")

    connection = None

    try:
        connection = get_postgres_connection()

        return pd.read_sql_query(
            sql=QUERY_GET_HIRED_PEOPLE,
            con=connection,
            params={"department": clean_department},
        )

    except Exception as error:
        raise RuntimeError(
            f"Error retrieving hired people from PostgreSQL: {error}"
        ) from error

    finally:
        if connection is not None:
            connection.close()

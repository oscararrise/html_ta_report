from __future__ import annotations

import os
from typing import Sequence

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection


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
    job_titles: Sequence[str],
) -> pd.DataFrame:
    normalized_job_titles = normalize_job_titles(job_titles)

    output_columns = [
        "app_id",
        "app_workflow_state_name",
        "app_full_name",
        "app_country",
        "app_sourcetype",
        "job_title",
        "app_hire_date",
    ]

    if not normalized_job_titles:
        print("No valid job titles were provided.")
        return pd.DataFrame(columns=output_columns)

    placeholders = ", ".join(["%s"] * len(normalized_job_titles))

    query = f"""
        SELECT DISTINCT
            app_id,
            state_name AS app_workflow_state_name,
            full_name AS app_full_name,
            country AS app_country,
            source_type AS app_sourcetype,
            title AS job_title,
            NULL::date AS app_hire_date
        FROM jv_arrise_data_schema.applications
        WHERE LOWER(TRIM(title)) IN ({placeholders})
          AND app_id IS NOT NULL
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
            params=tuple(normalized_job_titles),
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

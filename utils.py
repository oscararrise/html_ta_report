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
        app_full_name,
        app_country,
        app_hire_date,
        ROW_NUMBER() OVER (
            PARTITION BY app_id
            ORDER BY app_hire_date DESC
        ) AS row_number
    FROM hr_ops_jbv_schematic.vw_job_applications
    WHERE LOWER(TRIM(job_department_name)) = LOWER(TRIM(%(department)s))
      AND LOWER(TRIM(app_workflow_state_name)) = 'hired'
      AND app_hire_date >= DATE_TRUNC('year', CURRENT_DATE)
      AND app_hire_date IS NOT NULL
      AND app_id IS NOT NULL
)
SELECT
    app_id,
    job_title,
    app_full_name AS name,
    app_country AS location,
    TRIM(TO_CHAR(app_hire_date, 'Month')) AS month_of_hire,
    app_hire_date
FROM hired_people
WHERE row_number = 1
ORDER BY
    app_hire_date ASC,
    job_title ASC,
    name ASC;
"""


def get_redshift_connection() -> connection:
    """
    Create and return a connection to Amazon Redshift.

    Required environment variables:
        REDSHIFT_HOST
        REDSHIFT_PORT
        REDSHIFT_DBNAME
        REDSHIFT_USER
        REDSHIFT_PASSWORD

    Optional environment variable:
        REDSHIFT_SSLMODE
    """
    load_dotenv(override=True)

    required_variables = [
        "REDSHIFT_HOST",
        "REDSHIFT_PORT",
        "REDSHIFT_DBNAME",
        "REDSHIFT_USER",
        "REDSHIFT_PASSWORD",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing_variables)
        )

    return psycopg2.connect(
        host=os.getenv("REDSHIFT_HOST"),
        port=int(os.getenv("REDSHIFT_PORT", "5439")),
        dbname=os.getenv("REDSHIFT_DBNAME"),
        user=os.getenv("REDSHIFT_USER"),
        password=os.getenv("REDSHIFT_PASSWORD"),
        sslmode=os.getenv("REDSHIFT_SSLMODE", "require"),
        connect_timeout=15,
    )


def normalize_job_titles(
    job_titles: Sequence[str],
) -> list[str]:
    """
    Clean, normalize and remove duplicated job titles.

    Args:
        job_titles: Sequence of Jobvite job titles.

    Returns:
        A normalized list of unique job titles.
    """
    normalized_job_titles = [
        str(title).strip().casefold()
        for title in job_titles
        if title is not None and str(title).strip()
    ]

    return list(
        dict.fromkeys(normalized_job_titles)
    )


def get_open_job_applications(
    job_titles: Sequence[str],
) -> pd.DataFrame:
    """
    Retrieve all applications associated with the provided open job titles.

    Rejected and withdrawn applications are intentionally included so the
    report can calculate:

        - Active candidate count
        - Rejected application count
        - Withdrawn application count
        - Candidates by stage

    Args:
        job_titles: Sequence of open Jobvite job titles.

    Returns:
        A DataFrame containing applications associated with the job titles.
    """
    normalized_job_titles = normalize_job_titles(
        job_titles
    )

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

        return pd.DataFrame(
            columns=output_columns
        )

    placeholders = ", ".join(
        ["%s"] * len(normalized_job_titles)
    )

    query = f"""
        SELECT DISTINCT
            app_id,
            app_workflow_state_name,
            app_full_name,
            app_country,
            app_sourcetype,
            job_title,
            app_hire_date
        FROM hr_ops_jbv_schematic.vw_job_applications
        WHERE LOWER(TRIM(job_status)) = 'open'
          AND LOWER(TRIM(job_title)) IN ({placeholders})
          AND app_id IS NOT NULL
        ORDER BY
            job_title,
            app_full_name,
            app_workflow_state_name;
    """

    connection = None

    try:
        connection = get_redshift_connection()

        applications_df = pd.read_sql_query(
            sql=query,
            con=connection,
            params=tuple(normalized_job_titles),
        )

        return applications_df

    except Exception as error:
        raise RuntimeError(
            f"Error retrieving applications from Redshift: {error}"
        ) from error

    finally:
        if connection is not None:
            connection.close()


def get_hired_people_current_year(
    department: str,
) -> pd.DataFrame:
    """
    Retrieve people hired during the current calendar year
    for the specified department.

    Args:
        department: Job department name, for example "Legal".

    Returns:
        A DataFrame containing hired candidates.
    """
    clean_department = department.strip()

    if not clean_department:
        raise ValueError(
            "Department cannot be empty."
        )

    connection = None

    try:
        connection = get_redshift_connection()

        hired_people_df = pd.read_sql_query(
            sql=QUERY_GET_HIRED_PEOPLE,
            con=connection,
            params={
                "department": clean_department,
            },
        )

        return hired_people_df

    except Exception as error:
        raise RuntimeError(
            f"Error retrieving hired people from Redshift: {error}"
        ) from error

    finally:
        if connection is not None:
            connection.close()
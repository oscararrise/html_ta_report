from __future__ import annotations

from typing import Sequence

import pandas as pd

from utils import get_postgres_connection


HIRED_PEOPLE_OUTPUT_COLUMNS = [
    "app_id",
    "job_title",
    "name",
    "location",
    "month_of_hire",
    "app_hire_date",
]


def normalize_departments(departments: Sequence[str]) -> list[str]:
    """Return unique, non-empty department names in comparison form."""
    normalized_departments = [
        str(department).strip().casefold()
        for department in departments
        if department is not None and str(department).strip()
    ]

    return list(dict.fromkeys(normalized_departments))


def get_hired_people_current_year(
    departments: Sequence[str],
) -> pd.DataFrame:
    """Retrieve unique YTD hires belonging to any selected department."""
    normalized_departments = normalize_departments(departments)

    if not normalized_departments:
        raise ValueError("At least one department must be provided.")

    placeholders = ", ".join(
        ["%s"] * len(normalized_departments)
    )

    query = f"""
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
            WHERE LOWER(TRIM(department)) IN ({placeholders})
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

    connection = None

    try:
        connection = get_postgres_connection()

        return pd.read_sql_query(
            sql=query,
            con=connection,
            params=tuple(normalized_departments),
        )
    except Exception as error:
        raise RuntimeError(
            "Error retrieving hired people for Commercial departments "
            f"from PostgreSQL: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()

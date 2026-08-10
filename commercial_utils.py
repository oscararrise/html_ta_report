from __future__ import annotations

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


def get_hired_people_current_year(
    business_unit: str,
) -> pd.DataFrame:
    """Retrieve unique YTD hires belonging to a business unit."""
    normalized_business_unit = str(business_unit).strip().casefold()

    if not normalized_business_unit:
        raise ValueError("A business unit must be provided.")

    query = """
        WITH hired_people AS (
            SELECT
                hires.app_id,
                hires.job_title,
                hires.full_name,
                hires.candidate_country,
                hires.hire_date,
                ROW_NUMBER() OVER (
                    PARTITION BY hires.app_id
                    ORDER BY hires.hire_date DESC
                ) AS row_number
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
            params=(normalized_business_unit,),
        )
    except Exception as error:
        raise RuntimeError(
            "Error retrieving hired people for the Commercial business unit "
            f"from PostgreSQL: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()

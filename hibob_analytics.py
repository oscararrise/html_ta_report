from __future__ import annotations

import os
from typing import Any, Iterable

import pandas as pd
from psycopg2 import sql

from utils import get_postgres_connection


DEFAULT_HIBOB_SCHEMA = "hibob_etl"
DEFAULT_HIBOB_TABLE = "employees"
DEFAULT_BUSINESS_UNIT = "Commercial"
NOT_SPECIFIED = "Not specified"

STRUCTURE_COLUMNS = [
    "team",
    "location",
    "role",
    "headcount",
]

HISTORY_LIMITATION = (
    "The 2025 vs 2026 comparison is not available from this source. "
    "hibob_etl.employees stores only the current effective Work values, "
    "so dated Work/Lifecycle history or dated employee snapshots are "
    "required to calculate historical team and location changes accurately."
)


def _get_relation_columns(
    connection: Any,
    schema: str,
    table: str,
) -> set[str]:
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (schema, table))
        return {str(row[0]) for row in cursor.fetchall()}


def _columns_containing_value(
    connection: Any,
    schema: str,
    table: str,
    columns: Iterable[str],
    value: str,
) -> list[str]:
    matches: list[str] = []

    with connection.cursor() as cursor:
        for column in columns:
            query = sql.SQL(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM {}.{}
                    WHERE LOWER(BTRIM({})) = %s
                );
                """
            ).format(
                sql.Identifier(schema),
                sql.Identifier(table),
                sql.Identifier(column),
            )
            cursor.execute(query, (value.strip().casefold(),))

            if bool(cursor.fetchone()[0]):
                matches.append(column)

    return matches


def _resolve_business_unit_column(
    connection: Any,
    schema: str,
    table: str,
    columns: set[str],
    business_unit: str,
) -> str:
    configured_column = os.getenv(
        "HIBOB_BUSINESS_UNIT_COLUMN",
        "",
    ).strip()

    if configured_column:
        if configured_column not in columns:
            raise RuntimeError(
                "HIBOB_BUSINESS_UNIT_COLUMN does not exist in "
                f"{schema}.{table}: {configured_column}"
            )

        return configured_column

    candidate_groups = [
        sorted(
            column
            for column in columns
            if column.startswith("hr_")
            and (
                "customcolumns" in column
                or "custom_field" in column
            )
        ),
        sorted(
            column
            for column in columns
            if column.startswith("raw_")
            and (
                "customcolumns" in column
                or "custom_field" in column
            )
        ),
        sorted(
            column
            for column in columns
            if column.startswith("hr_")
            and any(
                token in column
                for token in [
                    "business",
                    "custom",
                    "department",
                    "org",
                ]
            )
        ),
        sorted(
            column
            for column in columns
            if column.startswith("raw_")
            and any(
                token in column
                for token in [
                    "business",
                    "custom",
                    "department",
                    "org",
                ]
            )
        ),
    ]

    for candidates in candidate_groups:
        matches = _columns_containing_value(
            connection=connection,
            schema=schema,
            table=table,
            columns=candidates,
            value=business_unit,
        )

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            raise RuntimeError(
                "More than one HiBob custom column contains the exact "
                f"business unit value {business_unit!r}: {', '.join(matches)}. "
                "Set HIBOB_BUSINESS_UNIT_COLUMN to the correct column name."
            )

    raise RuntimeError(
        "Could not identify the HiBob Business unit column automatically. "
        "Set HIBOB_BUSINESS_UNIT_COLUMN to the column in "
        f"{schema}.{table} that contains {business_unit!r}."
    )


def _coalesced_text_expression(
    columns: set[str],
    preferred_column: str,
    fallback_column: str,
    default: str,
) -> sql.Composed:
    available_columns = [
        column
        for column in [preferred_column, fallback_column]
        if column in columns
    ]

    if not available_columns:
        raise RuntimeError(
            "Required HiBob columns are missing: "
            f"{preferred_column}, {fallback_column}"
        )

    values = [
        sql.SQL("NULLIF(BTRIM({}), '')").format(
            sql.Identifier(column)
        )
        for column in available_columns
    ]
    values.append(sql.Literal(default))

    return sql.SQL("COALESCE({})").format(
        sql.SQL(", ").join(values)
    )


def get_current_commercial_structure(
    business_unit: str = DEFAULT_BUSINESS_UNIT,
) -> pd.DataFrame:
    """Return aggregate active headcount by team, location and role."""
    normalized_business_unit = str(business_unit).strip()

    if not normalized_business_unit:
        raise ValueError("A HiBob business unit must be provided.")

    schema = os.getenv(
        "HIBOB_POSTGRES_SCHEMA",
        DEFAULT_HIBOB_SCHEMA,
    ).strip()
    table = os.getenv(
        "HIBOB_POSTGRES_TABLE",
        DEFAULT_HIBOB_TABLE,
    ).strip()

    if not schema or not table:
        raise ValueError(
            "HIBOB_POSTGRES_SCHEMA and HIBOB_POSTGRES_TABLE cannot be empty."
        )

    connection = None

    try:
        connection = get_postgres_connection()
        columns = _get_relation_columns(
            connection=connection,
            schema=schema,
            table=table,
        )

        if not columns:
            raise RuntimeError(
                f"HiBob table was not found or has no columns: {schema}.{table}"
            )

        if "hibob_root_id" not in columns:
            raise RuntimeError(
                f"{schema}.{table} does not contain hibob_root_id."
            )

        business_unit_column = _resolve_business_unit_column(
            connection=connection,
            schema=schema,
            table=table,
            columns=columns,
            business_unit=normalized_business_unit,
        )

        team_expression = _coalesced_text_expression(
            columns=columns,
            preferred_column="hr_work_department",
            fallback_column="raw_work_department",
            default=NOT_SPECIFIED,
        )
        location_expression = _coalesced_text_expression(
            columns=columns,
            preferred_column="hr_work_site",
            fallback_column="raw_work_site",
            default=NOT_SPECIFIED,
        )
        role_expression = _coalesced_text_expression(
            columns=columns,
            preferred_column="hr_work_title",
            fallback_column="raw_work_title",
            default=NOT_SPECIFIED,
        )
        status_expression = _coalesced_text_expression(
            columns=columns,
            preferred_column="hr_internal_status",
            fallback_column="raw_internal_status",
            default="",
        )

        query = sql.SQL(
            """
            WITH current_employees AS (
                SELECT
                    hibob_root_id,
                    {team} AS team,
                    {location} AS location,
                    {role} AS role
                FROM {schema}.{table}
                WHERE LOWER(BTRIM({business_unit_column})) = %s
                  AND LOWER({status}) = 'active'
                  AND hibob_root_id IS NOT NULL
            )
            SELECT
                team,
                location,
                role,
                COUNT(DISTINCT hibob_root_id)::integer AS headcount
            FROM current_employees
            GROUP BY team, location, role
            ORDER BY location, team, headcount DESC, role;
            """
        ).format(
            team=team_expression,
            location=location_expression,
            role=role_expression,
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            business_unit_column=sql.Identifier(
                business_unit_column
            ),
            status=status_expression,
        )

        dataframe = pd.read_sql_query(
            sql=query.as_string(connection),
            con=connection,
            params=(normalized_business_unit.casefold(),),
        )

        return dataframe.reindex(columns=STRUCTURE_COLUMNS)
    except Exception as error:
        raise RuntimeError(
            "Error retrieving the current Commercial organization from "
            f"HiBob PostgreSQL data: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()


def _build_ranked_dimension_rows(
    structure: pd.DataFrame,
    column_name: str,
    label_key: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    counts = (
        structure.groupby(column_name, as_index=False)["headcount"]
        .sum()
        .sort_values(
            ["headcount", column_name],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    if limit > 1 and len(counts) > limit:
        visible_counts = counts.head(limit - 1).copy()
        other_total = int(counts.iloc[limit - 1 :]["headcount"].sum())
        counts = pd.concat(
            [
                visible_counts,
                pd.DataFrame(
                    [{column_name: "Other", "headcount": other_total}]
                ),
            ],
            ignore_index=True,
        )

    total_headcount = int(counts["headcount"].sum())
    maximum_headcount = (
        int(counts["headcount"].max()) if not counts.empty else 0
    )

    return [
        {
            label_key: str(getattr(row, column_name)),
            "total": int(row.headcount),
            "share": round(
                int(row.headcount) / total_headcount * 100,
                1,
            ) if total_headcount else 0,
            "width": round(
                int(row.headcount) / maximum_headcount * 100,
                2,
            ) if maximum_headcount else 0,
        }
        for row in counts.itertuples(index=False)
    ]


def build_hibob_analytics_context(
    structure_df: pd.DataFrame | None,
) -> dict[str, Any]:
    """Build aggregate, employee-free values for the HTML report."""
    empty_context = {
        "hibob_has_data": False,
        "hibob_total_headcount": 0,
        "hibob_total_teams": 0,
        "hibob_total_locations": 0,
        "hibob_total_roles": 0,
        "hibob_location_team_rows": [],
        "hibob_matrix_locations": [],
        "hibob_matrix_rows": [],
        "hibob_team_rows": [],
        "hibob_location_rows": [],
        "hibob_role_rows": [],
        "hibob_insights": [],
        "hibob_history_note": HISTORY_LIMITATION,
    }

    if structure_df is None or structure_df.empty:
        return empty_context

    missing_columns = set(STRUCTURE_COLUMNS).difference(
        structure_df.columns
    )

    if missing_columns:
        raise ValueError(
            "HiBob structure data is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    structure = structure_df[STRUCTURE_COLUMNS].copy()

    for column in ["team", "location", "role"]:
        structure[column] = (
            structure[column]
            .fillna(NOT_SPECIFIED)
            .astype(str)
            .str.strip()
            .replace("", NOT_SPECIFIED)
        )

    structure["headcount"] = (
        pd.to_numeric(
            structure["headcount"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )
    structure = structure[structure["headcount"] > 0]

    if structure.empty:
        return empty_context

    structure = (
        structure.groupby(
            ["team", "location", "role"],
            as_index=False,
        )["headcount"]
        .sum()
    )

    locations = sorted(
        structure["location"].unique().tolist(),
        key=str.casefold,
    )
    teams = sorted(
        structure["team"].unique().tolist(),
        key=str.casefold,
    )

    location_team_rows: list[dict[str, Any]] = []

    for (location, team), group in structure.groupby(
        ["location", "team"],
        sort=True,
    ):
        role_counts = (
            group.groupby("role", as_index=False)["headcount"]
            .sum()
            .sort_values(
                ["headcount", "role"],
                ascending=[False, True],
            )
        )
        roles = " · ".join(
            f"{row.role} ({int(row.headcount)})"
            for row in role_counts.itertuples(index=False)
        )
        location_team_rows.append(
            {
                "location": location,
                "team": team,
                "roles": roles,
                "headcount": int(role_counts["headcount"].sum()),
            }
        )

    matrix = structure.pivot_table(
        index="team",
        columns="location",
        values="headcount",
        aggfunc="sum",
        fill_value=0,
    )

    matrix_rows = []
    maximum_matrix_value = int(matrix.to_numpy().max())

    for team in teams:
        values = [
            int(matrix.at[team, location])
            if location in matrix.columns
            else 0
            for location in locations
        ]
        matrix_rows.append(
            {
                "team": team,
                "location_counts": values,
                "cells": [
                    {
                        "headcount": value,
                        "opacity": round(
                            0.08 + (value / maximum_matrix_value * 0.64),
                            2,
                        ) if value and maximum_matrix_value else 0.04,
                    }
                    for value in values
                ],
                "total": sum(values),
            }
        )

    team_rows = _build_ranked_dimension_rows(
        structure,
        column_name="team",
        label_key="team",
    )
    location_rows = _build_ranked_dimension_rows(
        structure,
        column_name="location",
        label_key="location",
    )
    role_rows = _build_ranked_dimension_rows(
        structure,
        column_name="role",
        label_key="role",
    )

    team_footprint = (
        structure.groupby("team")["location"]
        .nunique()
        .sort_values(ascending=False)
    )
    broadest_team = str(team_footprint.index[0])
    broadest_team_locations = int(team_footprint.iloc[0])

    largest_team = team_rows[0]
    largest_location = location_rows[0]
    largest_role = role_rows[0]

    organization_insights = [
        {
            "label": "Largest team",
            "value": f"{largest_team['share']:.0f}%",
            "headline": largest_team["team"],
            "detail": (
                f"{largest_team['total']} people, the largest share of "
                "current Commercial headcount."
            ),
        },
        {
            "label": "Largest location",
            "value": f"{largest_location['share']:.0f}%",
            "headline": largest_location["location"],
            "detail": (
                f"{largest_location['total']} people are currently based "
                "in this location."
            ),
        },
        {
            "label": "Widest footprint",
            "value": str(broadest_team_locations),
            "headline": broadest_team,
            "detail": (
                "This team spans the greatest number of current locations."
            ),
        },
        {
            "label": "Most common role",
            "value": f"{largest_role['share']:.0f}%",
            "headline": largest_role["role"],
            "detail": (
                f"{largest_role['total']} people share this role title "
                "across Commercial."
            ),
        },
    ]

    return {
        "hibob_has_data": True,
        "hibob_total_headcount": int(structure["headcount"].sum()),
        "hibob_total_teams": len(teams),
        "hibob_total_locations": len(locations),
        "hibob_total_roles": int(structure["role"].nunique()),
        "hibob_location_team_rows": location_team_rows,
        "hibob_matrix_locations": locations,
        "hibob_matrix_rows": matrix_rows,
        "hibob_team_rows": team_rows,
        "hibob_location_rows": location_rows,
        "hibob_role_rows": role_rows,
        "hibob_insights": organization_insights,
        "hibob_history_note": HISTORY_LIMITATION,
    }

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


# Jobvite API endpoint used to retrieve requisitions
JOBVITE_URL = "https://api.jobvite.com/api/v2/job"

# Maximum number of requisitions returned per API request
PAGE_SIZE = 500

# Only retrieve requisitions with Open status
JOB_STATUSES = ["Open"]

# Final DataFrame column order
DATAFRAME_COLUMNS = [
    "job_eid",
    "requisition_id",
    "title",
    "job_state",
    "department",
    "sub_department",
    "location",
    "location_city",
    "location_country",
    "hiring_manager_first_name",
    "hiring_manager_last_name",
    "hiring_manager_user_id",
    "hiring_manager_user_name",
    "reason",
    "working_type",
    "exclude_from_tth",
    "exclude_from_live_and_ytd",
]


def get_required_env(name: str) -> str:
    """
    Retrieve a required environment variable.

    Raises an error when the variable is missing or empty.
    """
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Check your .env file."
        )

    return value


def get_custom_field(
    requisition: dict[str, Any],
    field_code: str,
) -> str:
    """
    Retrieve a custom field value from the requisition.

    Jobvite stores custom fields inside the customField list.

    If the fieldCode is missing or the field has no value,
    return an empty string.
    """
    custom_fields = requisition.get("customField") or []

    for field in custom_fields:
        if field.get("fieldCode") == field_code:
            value = field.get("value")

            if value is None:
                return ""

            return str(value)

    return ""


def normalize_requisition(
    requisition: dict[str, Any],
) -> dict[str, str]:
    """
    Convert a Jobvite requisition into a flat dictionary.

    The returned dictionary represents one DataFrame row.
    """
    hiring_manager = (
        requisition.get("primaryHiringManager") or {}
    )

    return {
        # Standard requisition identifiers
        "job_eid": requisition.get("eId") or "",
        "requisition_id": (
            requisition.get("requisitionId") or ""
        ),

        # Standard requisition information
        "title": requisition.get("title") or "",
        "job_state": requisition.get("jobState") or "",
        "department": (
            requisition.get("department") or ""
        ),

        # Custom field stored inside customField
        "sub_department": get_custom_field(
            requisition=requisition,
            field_code="sub_department",
        ),

        # Standard location fields
        "location": requisition.get("location") or "",
        "location_city": (
            requisition.get("locationCity") or ""
        ),
        "location_country": (
            requisition.get("locationCountry") or ""
        ),

        # Primary hiring manager fields
        "hiring_manager_first_name": (
            hiring_manager.get("firstName") or ""
        ),
        "hiring_manager_last_name": (
            hiring_manager.get("lastName") or ""
        ),
        "hiring_manager_user_id": (
            hiring_manager.get("userId") or ""
        ),
        "hiring_manager_user_name": (
            hiring_manager.get("userName") or ""
        ),

        # Custom requisition fields
        "reason": get_custom_field(
            requisition=requisition,
            field_code="reason",
        ),
        "working_type": get_custom_field(
            requisition=requisition,
            field_code="working_type",
        ),
        "exclude_from_tth": get_custom_field(
            requisition=requisition,
            field_code="exclude_from_tth",
        ),
        "exclude_from_live_and_ytd": get_custom_field(
            requisition=requisition,
            field_code="exclude_from_live_and_ytd",
        ),
    }


def fetch_all_requisitions(
    api_key: str,
    api_secret: str,
) -> list[dict[str, Any]]:
    """
    Retrieve every Open requisition from Jobvite.

    The function handles pagination automatically.
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": (
            "application/json; charset=utf-8"
        ),
        "x-jvi-api": api_key,
        "x-jvi-sc": api_secret,
    }

    all_requisitions: list[dict[str, Any]] = []
    start = 1

    while True:
        # Jobvite uses start and count for pagination
        params: list[tuple[str, str | int]] = [
            ("start", start),
            ("count", PAGE_SIZE),
        ]

        # Add the requested requisition status filters
        params.extend(
            ("jobStatus", status)
            for status in JOB_STATUSES
        )

        print(
            f"Requesting Jobvite requisitions: "
            f"start={start}, count={PAGE_SIZE}"
        )

        response = requests.get(
            JOBVITE_URL,
            headers=headers,
            params=params,
            timeout=90,
        )

        # Raise an exception for HTTP errors
        response.raise_for_status()

        payload = response.json()

        api_status = payload.get("status") or {}

        # Validate the status returned inside the Jobvite response
        if str(api_status.get("code")) != "200":
            raise RuntimeError(
                "Jobvite returned an API error: "
                f"{api_status.get('messages')}"
            )

        requisitions = (
            payload.get("requisitions") or []
        )

        if not isinstance(requisitions, list):
            raise TypeError(
                "The requisitions property is not a list."
            )

        all_requisitions.extend(requisitions)

        print(
            f"Page received: {len(requisitions)} | "
            f"Total collected: {len(all_requisitions)}"
        )

        # The last page contains fewer records than PAGE_SIZE
        if len(requisitions) < PAGE_SIZE:
            break

        start += PAGE_SIZE

    return all_requisitions


def get_requisitions_dataframe() -> pd.DataFrame:
    """
    Retrieve Open requisitions and return them as a DataFrame.
    """
    # Load variables from the .env file
    load_dotenv()

    api_key = get_required_env("JOBVITE_API_KEY")
    api_secret = get_required_env(
        "JOBVITE_API_SECRET"
    )

    # Retrieve raw requisitions from Jobvite
    requisitions = fetch_all_requisitions(
        api_key=api_key,
        api_secret=api_secret,
    )

    # Convert each requisition into a flat row
    rows = [
        normalize_requisition(requisition)
        for requisition in requisitions
    ]

    # Create the DataFrame using the expected column order
    dataframe = pd.DataFrame(
        rows,
        columns=DATAFRAME_COLUMNS,
    )

    return dataframe


if __name__ == "__main__":
    # Allow this file to be executed independently for testing
    df = get_requisitions_dataframe()

    print()
    print("Extraction completed.")
    print(f"Total Open requisitions: {len(df)}")
    print()
    print(df.head())
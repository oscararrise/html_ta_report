from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

import pandas as pd

from dotenv import load_dotenv

from commercial_feedback_report import generate_report
from generate_report import prepare_applications, prepare_requisitions
from commercial_utils import get_hired_people_current_year
from hibob_analytics import get_current_commercial_structure
# from send_report_power_automate import send_html_report
from update_requisitions import get_requisitions_dataframe
from utils import (
    export_applications_debug_log,
    get_open_job_applications,
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


def export_report_data_copy(
    *,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
    hibob_structure_df: pd.DataFrame,
    reference: datetime | None,
) -> Path:
    """Create one Excel workbook with the datasets used by the report."""
    generated_at = datetime.now()
    DATA_COPY_ROOT.mkdir(parents=True, exist_ok=True)

    report_requisitions = prepare_requisitions(requisitions_df)
    report_applications = prepare_applications(applications_df)

    output_file = (
        DATA_COPY_ROOT
        / f"commercial_report_data_{generated_at:%Y-%m-%d_%H-%M-%S}.xlsx"
    )

    datasets = [
        (
            "Requisitions",
            report_requisitions,
            "Open Commercial requisitions after report consolidation.",
        ),
        (
            "Applications",
            report_applications,
            "Commercial active-candidate pipeline after report stage filters.",
        ),
        (
            "Hires YTD",
            hired_people_df,
            "Commercial hires used for YTD and monthly hiring metrics.",
        ),
        (
            "HiBob",
            hibob_structure_df,
            "Current active Commercial HiBob structure used by the report.",
        ),
    ]

    reference_date = (
        reference.strftime("%Y-%m-%d")
        if reference is not None
        else generated_at.strftime("%Y-%m-%d")
    )

    summary_rows: list[dict[str, object]] = []

    print()
    print("Creating report data copy...")
    print("--------------------------------")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, dataframe, description in datasets:
            dataframe.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

            worksheet = writer.book[sheet_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            summary_rows.append(
                {
                    "sheet": sheet_name,
                    "rows": len(dataframe),
                    "columns": len(dataframe.columns),
                    "description": description,
                    "report_reference_date": reference_date,
                }
            )

            print(f"  {sheet_name}: {len(dataframe):,} rows")

        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        summary_sheet = writer.book["Summary"]
        summary_sheet.freeze_panes = "A2"
        summary_sheet.auto_filter.ref = summary_sheet.dimensions

    file_size_mb = output_file.stat().st_size / (1024 * 1024)

    print(
        f"Data copy created: {output_file} "
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

    # Get all open requisitions and store them in a DataFrame.
    requisitions_df = get_requisitions_dataframe()

    print(
        "Open requisitions found for Commercial business unit:",
        len(requisitions_df),
    )

    # Extract unique open Jobvite job identifiers.
    job_eids = (
        requisitions_df["job_eid"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda values: values.ne("")]
        .drop_duplicates()
        .tolist()
    )

    # Get active applications for the selected open requisitions.
    applications_df = get_open_job_applications(job_eids)

    export_applications_debug_log(
        applications_df=applications_df,
        requisitions_df=requisitions_df,
    )

    # Get people hired during the current year for the Commercial business unit.
    hired_people_df = get_hired_people_current_year(REPORT_AREA)

    # Get current aggregate organization data from the local HiBob table.
    hibob_structure_df = get_current_commercial_structure(REPORT_AREA)

    print(
        "HiBob Commercial team/location/role groups found:",
        len(hibob_structure_df),
    )

    # Generate the combined Commercial Talent Acquisition report.
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

    export_report_data_copy(
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
        hibob_structure_df=hibob_structure_df,
        reference=report_reference,
    )

    # send_html_report(report_file)


if __name__ == "__main__":
    main()

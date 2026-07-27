from __future__ import annotations

from dotenv import load_dotenv

from commercial_utils import get_hired_people_current_year
from generate_report import generate_report
from html_postprocessor import add_candidate_table_scroll
from send_report_power_automate import send_html_report
from update_requisitions import get_requisitions_dataframe
from utils import (
    export_applications_debug_log,
    get_open_job_applications,
)


REPORT_AREA = "Commercial"
DEPARTMENTS = [
    "Commercial Operations",
    "Commercial BI",
    "Commercial - International",
]


def main() -> None:
    load_dotenv(override=True)

    print("Starting report generation... by area:", REPORT_AREA)
    print("Departments included:", ", ".join(DEPARTMENTS))

    # Get all open requisitions and store them in a DataFrame.
    requisitions_df = get_requisitions_dataframe()

    # Filter open requisitions by the configured department list.
    normalized_departments = {
        department.strip().casefold()
        for department in DEPARTMENTS
        if department.strip()
    }

    requisition_departments = (
        requisitions_df["department"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    requisitions_df = requisitions_df[
        requisition_departments.isin(normalized_departments)
    ].copy()

    print(
        "Open requisitions found for configured departments:",
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

    # Get people hired during the current year for all selected departments.
    hired_people_df = get_hired_people_current_year(DEPARTMENTS)

    # Generate the combined Commercial Talent Acquisition report.
    report_file = generate_report(
        area=REPORT_AREA,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
    )

    # Keep the candidate table compact: 10 visible rows and vertical scroll.
    report_file = add_candidate_table_scroll(
        report_path=report_file,
        visible_rows=10,
    )

    print("HTML report generated successfully:")
    print(report_file)

    send_html_report(report_file)


if __name__ == "__main__":
    main()

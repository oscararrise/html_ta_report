from __future__ import annotations

from dotenv import load_dotenv

from commercial_utils import get_hired_people_current_year
from generate_report import generate_report
from hibob_analytics import get_current_commercial_structure
from html_postprocessor import add_candidate_table_scroll
from send_report_power_automate import send_html_report
from update_requisitions import get_requisitions_dataframe
from utils import (
    export_applications_debug_log,
    get_open_job_applications,
)


REPORT_AREA = "Commercial"


def main() -> None:
    load_dotenv(override=True)

    print("Starting report generation... by area:", REPORT_AREA)

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

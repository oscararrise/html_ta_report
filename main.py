from __future__ import annotations
from dotenv import load_dotenv
from generate_report import generate_report
from update_requisitions import get_requisitions_dataframe
from utils import *
from send_report_power_automate import send_html_report


AREA = "Legal"
def main() -> None:
    load_dotenv(override=True)

    print("Starting report generation... by area:", AREA)
    # Get all open requisitions and store them in a DataFrame.
    requisitions_df = get_requisitions_dataframe()
    # Filter open requisitions by department.
    requisitions_df = requisitions_df[requisitions_df["department"].fillna("").str.strip().str.casefold() == AREA.casefold()].copy()
    # Extract unique job titles into a list.
    job_eids = (
    requisitions_df["job_eid"]
    .dropna()
    .astype(str)
    .str.strip()
    .loc[lambda values: values.ne("")]
    .drop_duplicates()
    .tolist()
)

    applications_df = get_open_job_applications(job_eids)
    # Get active applications for the open job titles.


    export_applications_debug_log(
    applications_df=applications_df,
    requisitions_df=requisitions_df,
)
    # Get people hired during the current year.
    hired_people_df = get_hired_people_current_year(AREA)
    # Generate the HTML Talent Acquisition report.
    report_file = generate_report(area=AREA,requisitions_df=requisitions_df,applications_df=applications_df,hired_people_df=hired_people_df,)
    print("HTML report generated successfully:")
    print(report_file)
    send_html_report(report_file)

if __name__ == "__main__":
    main()
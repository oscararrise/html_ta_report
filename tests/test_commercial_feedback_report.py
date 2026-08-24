from __future__ import annotations

from datetime import datetime
import unittest

import pandas as pd
from jinja2 import Environment

from commercial_feedback_report import (
    REPORT_TEMPLATE,
    build_compact_context,
    build_ranked_dimension_with_other,
    build_team_footprint_rows,
    count_hires_current_month,
    get_peak_hiring_month,
)


class CommercialFeedbackReportTests(unittest.TestCase):
    def test_counts_hires_only_in_current_month(self) -> None:
        hires = pd.DataFrame(
            {
                "app_hire_date": [
                    pd.Timestamp("2026-08-01"),
                    pd.Timestamp("2026-08-24"),
                    pd.Timestamp("2026-07-31"),
                ]
            }
        )
        self.assertEqual(
            count_hires_current_month(hires, datetime(2026, 8, 24)),
            2,
        )

    def test_returns_peak_hiring_month(self) -> None:
        peak = get_peak_hiring_month(
            [
                {"month": "January", "month_short": "Jan", "total": 3},
                {"month": "February", "month_short": "Feb", "total": 7},
            ]
        )
        self.assertEqual(peak, {"month": "Feb", "total": 7})

    def test_other_keeps_visible_breakdown(self) -> None:
        structure = pd.DataFrame(
            [
                {"team": f"Team {index}", "headcount": 10 - index}
                for index in range(9)
            ]
        )
        rows = build_ranked_dimension_with_other(
            structure,
            "team",
            "team",
            limit=5,
        )
        other = rows[-1]
        self.assertEqual(other["team"], "Other")
        self.assertTrue(other["other_items"])
        self.assertEqual(
            other["total"],
            sum(item["total"] for item in other["other_items"]),
        )

    def test_builds_compact_team_footprint(self) -> None:
        structure = pd.DataFrame(
            [
                {"team": "Commercial BI", "location": "Malta", "role": "Analyst", "headcount": 5},
                {"team": "Commercial BI", "location": "Serbia", "role": "Analyst", "headcount": 3},
                {"team": "Commercial BI", "location": "Malta", "role": "Manager", "headcount": 2},
            ]
        )
        row = build_team_footprint_rows(structure)[0]
        self.assertEqual(row["headcount"], 10)
        self.assertEqual(row["site_count"], 2)
        self.assertEqual(row["largest_site"], "Malta")
        self.assertEqual(row["top_role"], "Analyst")

    def test_compact_template_matches_requested_sections(self) -> None:
        requisitions = pd.DataFrame(
            [
                {
                    "requisition_id": "R-1",
                    "job_eid": "R-1",
                    "title": "Analyst",
                    "hiring_manager_user_name": "Manager",
                    "reason": "New",
                    "working_type": "Hybrid",
                    "location": "Malta",
                    "location_country": "Malta",
                    "exclude_from_live_and_ytd": "No",
                }
            ]
        )
        hires = pd.DataFrame(
            [
                {
                    "app_id": "H-1",
                    "job_title": "Analyst",
                    "name": "Test Hire",
                    "location": "Malta",
                    "month_of_hire": "August",
                    "app_hire_date": pd.Timestamp("2026-08-15"),
                }
            ]
        )
        structure = pd.DataFrame(
            [
                {"team": "Commercial BI", "location": "Malta", "role": "Analyst", "headcount": 5}
            ]
        )

        context = build_compact_context(
            area="Commercial",
            requisitions_df=requisitions,
            applications_df=pd.DataFrame(),
            hired_people_df=hires,
            hibob_structure_df=structure,
            reference=datetime(2026, 8, 24),
            monthly_roles_override=4,
        )
        html = Environment().from_string(REPORT_TEMPLATE).render(**context)

        self.assertNotIn("Executive brief", html)
        self.assertNotIn('id="candidates"', html)
        self.assertNotIn("Pipeline shape", html)
        self.assertIn("Peak hiring month", html)
        self.assertIn("New roles opened this month", html)
        self.assertIn("Hires made this month", html)
        self.assertIn("Geographic footprint", html)
        self.assertIn("Team footprint summary", html)
        self.assertIn('id="vacancies"', html)
        self.assertIn('id="hires"', html)


if __name__ == "__main__":
    unittest.main()

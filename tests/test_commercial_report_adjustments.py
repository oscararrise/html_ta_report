from __future__ import annotations

import unittest

import pandas as pd
from jinja2 import Environment

from generate_report import (
    REPORT_TEMPLATE,
    build_report_context,
    prepare_applications,
)


class CommercialReportAdjustmentsTests(unittest.TestCase):
    def test_excludes_requested_candidate_stages(self) -> None:
        applications = pd.DataFrame(
            {
                "app_workflow_state_name": [
                    "New",
                    "Resume screen",
                    "Info requested / left message",
                    "Sourcing - submitted to manager",
                    "Candidate withdrew",
                    "Rejected",
                    "TA phone screen",
                    "1st interview - in-person",
                ]
            }
        )

        filtered = prepare_applications(applications)

        self.assertEqual(
            filtered["app_workflow_state_name"].tolist(),
            [
                "TA phone screen",
                "1st interview - in-person",
            ],
        )

    def test_builds_role_and_hire_country_rows(self) -> None:
        context = build_report_context(
            area="Commercial",
            requisitions_df=pd.DataFrame(
                [
                    self._requisition("R-1", "Analyst", "Malta"),
                    self._requisition("R-2", "Manager", "Malta"),
                    self._requisition("R-3", "Specialist", "Serbia"),
                ]
            ),
            applications_df=pd.DataFrame(),
            hired_people_df=pd.DataFrame(
                [
                    self._hire("H-1", "Malta"),
                    self._hire("H-2", "Malta"),
                    self._hire("H-3", "Serbia"),
                ]
            ),
        )

        self.assertEqual(
            context["active_role_country_rows"],
            [
                {"country": "Malta", "total": 2, "width": 100.0},
                {"country": "Serbia", "total": 1, "width": 50.0},
            ],
        )
        self.assertEqual(
            context["hire_country_rows"],
            [
                {"country": "Malta", "total": 2, "width": 100.0},
                {"country": "Serbia", "total": 1, "width": 50.0},
            ],
        )

    def test_rendered_report_contains_only_requested_insights(self) -> None:
        context = build_report_context(
            area="Commercial",
            requisitions_df=pd.DataFrame(
                [self._requisition("R-1", "Analyst", "Malta")]
            ),
            applications_df=pd.DataFrame(),
            hired_people_df=pd.DataFrame(
                [self._hire("H-1", "Malta")]
            ),
        )

        html = Environment().from_string(REPORT_TEMPLATE).render(**context)

        self.assertNotIn("Talent Acquisition Analytics", html)
        self.assertNotIn("Active Candidates by Country", html)
        self.assertIn("Active Roles by Country", html)
        self.assertIn("Hires by Country", html)

    @staticmethod
    def _requisition(
        requisition_id: str,
        title: str,
        country: str,
    ) -> dict[str, str]:
        return {
            "requisition_id": requisition_id,
            "job_eid": requisition_id,
            "title": title,
            "hiring_manager_user_name": "Manager",
            "reason": "New",
            "working_type": "Hybrid",
            "location": country,
            "location_country": country,
            "exclude_from_live_and_ytd": "No",
        }

    @staticmethod
    def _hire(app_id: str, country: str) -> dict[str, object]:
        return {
            "app_id": app_id,
            "job_title": "Analyst",
            "name": "Test Hire",
            "location": country,
            "month_of_hire": "January",
            "app_hire_date": pd.Timestamp("2026-01-15"),
        }


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import pandas as pd
from jinja2 import Environment

from generate_report import (
    REPORT_TEMPLATE,
    build_executive_insights,
    build_geography_comparison_rows,
    build_pipeline_by_title,
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
        self.assertIn("Executive brief", html)
        self.assertIn("Operational detail", html)
        self.assertIn("<details id=\"candidates\">", html)

    def test_builds_aligned_geography_chart_without_conversion_metric(self) -> None:
        rows = build_geography_comparison_rows(
            active_role_country_rows=[
                {"country": "Malta", "total": 4},
                {"country": "Serbia", "total": 2},
            ],
            hire_country_rows=[
                {"country": "Malta", "total": 3},
                {"country": "Romania", "total": 1},
            ],
        )

        self.assertEqual(
            rows,
            [
                {
                    "country": "Malta",
                    "open_roles": 4,
                    "hires": 3,
                    "open_width": 100.0,
                    "hire_width": 75.0,
                },
                {
                    "country": "Serbia",
                    "open_roles": 2,
                    "hires": 0,
                    "open_width": 50.0,
                    "hire_width": 0.0,
                },
                {
                    "country": "Romania",
                    "open_roles": 0,
                    "hires": 1,
                    "open_width": 0.0,
                    "hire_width": 25.0,
                },
            ],
        )

    def test_builds_descriptive_executive_insights(self) -> None:
        insights = build_executive_insights(
            total_open_roles=4,
            total_active_candidates=10,
            new_roles=3,
            backfill_roles=1,
            hires_by_month_rows=[
                {
                    "month": "January",
                    "month_short": "Jan",
                    "total": 2,
                    "height": 50,
                },
                {
                    "month": "February",
                    "month_short": "Feb",
                    "total": 4,
                    "height": 100,
                },
            ],
            pipeline_by_title=[
                {
                    "open_positions": 2,
                    "active_candidates": 0,
                },
                {
                    "open_positions": 2,
                    "active_candidates": 10,
                },
            ],
        )

        self.assertEqual(insights[0]["value"], "2.5x")
        self.assertEqual(insights[1]["value"], "2")
        self.assertEqual(insights[2]["value"], "Feb")
        self.assertEqual(insights[3]["value"], "75%")

    def test_pipeline_title_matching_is_case_insensitive(self) -> None:
        rows = build_pipeline_by_title(
            requisitions=pd.DataFrame(
                {"title": ["Commercial Analyst"]}
            ),
            applications=pd.DataFrame(
                {"job_title": [" commercial analyst "]}
            ),
        )

        self.assertEqual(rows[0]["active_candidates"], 1)
        self.assertEqual(rows[0]["status"], "Needs attention")

    def test_renders_global_consultant_as_non_geographic_site(self) -> None:
        context = build_report_context(
            area="Commercial",
            requisitions_df=pd.DataFrame(),
            applications_df=pd.DataFrame(),
            hired_people_df=pd.DataFrame(),
            hibob_structure_df=pd.DataFrame(
                [
                    {
                        "team": "Commercial BI",
                        "location": "Global Consultant",
                        "role": "Analyst",
                        "headcount": 5,
                    },
                    {
                        "team": "Commercial BI",
                        "location": "Malta",
                        "role": "Analyst",
                        "headcount": 3,
                    },
                ]
            ),
        )

        html = Environment().from_string(REPORT_TEMPLATE).render(**context)

        self.assertIn("Physical sites", html)
        self.assertIn("Largest physical site", html)
        self.assertIn("Global consultants", html)
        self.assertIn("Headcount by HiBob site", html)
        self.assertIn("Global Consultant (non-geographic)", html)
        self.assertIn("Site reflects the classification stored in HiBob", html)
        self.assertNotIn("Headcount by location", html)

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

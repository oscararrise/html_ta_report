from __future__ import annotations

import unittest

import pandas as pd

from hibob_analytics import (
    HISTORY_LIMITATION,
    build_hibob_analytics_context,
)


class BuildHiBobAnalyticsContextTests(unittest.TestCase):
    def test_builds_headcount_matrix_and_role_summary(self) -> None:
        structure = pd.DataFrame(
            [
                {
                    "team": "Commercial BI",
                    "location": "Malta",
                    "role": "Analyst",
                    "headcount": 2,
                },
                {
                    "team": "Commercial BI",
                    "location": "Malta",
                    "role": "Manager",
                    "headcount": 1,
                },
                {
                    "team": "Commercial BI",
                    "location": "Belgrade",
                    "role": "Analyst",
                    "headcount": 1,
                },
                {
                    "team": "Commercial Operations",
                    "location": "Malta",
                    "role": "Specialist",
                    "headcount": 3,
                },
            ]
        )

        context = build_hibob_analytics_context(structure)

        self.assertTrue(context["hibob_has_data"])
        self.assertEqual(context["hibob_total_headcount"], 7)
        self.assertEqual(context["hibob_total_teams"], 2)
        self.assertEqual(context["hibob_total_locations"], 2)
        self.assertEqual(context["hibob_total_roles"], 3)
        self.assertEqual(
            context["hibob_matrix_locations"],
            ["Belgrade", "Malta"],
        )
        self.assertEqual(
            context["hibob_matrix_rows"],
            [
                {
                    "team": "Commercial BI",
                    "location_counts": [1, 3],
                    "cells": [
                        {"headcount": 1, "opacity": 0.29},
                        {"headcount": 3, "opacity": 0.72},
                    ],
                    "total": 4,
                },
                {
                    "team": "Commercial Operations",
                    "location_counts": [0, 3],
                    "cells": [
                        {"headcount": 0, "opacity": 0.04},
                        {"headcount": 3, "opacity": 0.72},
                    ],
                    "total": 3,
                },
            ],
        )
        self.assertEqual(
            context["hibob_team_rows"],
            [
                {
                    "team": "Commercial BI",
                    "total": 4,
                    "share": 57.1,
                    "width": 100.0,
                },
                {
                    "team": "Commercial Operations",
                    "total": 3,
                    "share": 42.9,
                    "width": 75.0,
                },
            ],
        )
        self.assertEqual(
            context["hibob_insights"][0]["headline"],
            "Commercial BI",
        )
        self.assertEqual(
            context["hibob_location_team_rows"][1]["roles"],
            "Analyst (2) · Manager (1)",
        )
        self.assertEqual(
            context["hibob_history_note"],
            HISTORY_LIMITATION,
        )

    def test_empty_input_returns_empty_analytics(self) -> None:
        context = build_hibob_analytics_context(pd.DataFrame())

        self.assertFalse(context["hibob_has_data"])
        self.assertEqual(context["hibob_total_headcount"], 0)
        self.assertEqual(context["hibob_matrix_rows"], [])


if __name__ == "__main__":
    unittest.main()

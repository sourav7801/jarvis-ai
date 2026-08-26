from __future__ import annotations

import unittest

from omni.venture_research_program import build_venture_research_program


class VentureResearchProgramTests(unittest.TestCase):
    def test_physical_idea_gets_feasibility_supply_regulatory_and_long_horizon_tracks(self):
        program = build_venture_research_program(
            "Movable modular homes that can be transported and installed safely"
        )
        self.assertEqual(program["venture_type"], "PHYSICAL_OR_HYBRID")
        self.assertEqual(program["truth_policy"], "HYPOTHESES_ARE_NOT_FACTS")
        titles = {track["title"] for track in program["research_tracks"]}
        self.assertIn("Technical and scientific feasibility", titles)
        self.assertIn("Patents, IP, regulation and permissions", titles)
        self.assertIn("Supply chain, production and service operations", titles)
        horizons = {item["horizon"] for item in program["horizons"]}
        self.assertTrue({"YEAR 1", "YEAR 4", "YEAR 5"}.issubset(horizons))
        self.assertTrue(all(item["status"] == "UNTESTED" for item in program["hypotheses"]))

    def test_work_orders_are_owned_bounded_and_do_not_claim_completion(self):
        program = build_venture_research_program("A privacy-first inventory planning service")
        orders = program["department_work_orders"]
        self.assertGreaterEqual(len(orders), 8)
        self.assertTrue(all(item["agent"] and item["status"] == "QUEUED" for item in orders))
        self.assertIn("not invent", program["opportunity_radar"]["notice"].lower())


if __name__ == "__main__":
    unittest.main()

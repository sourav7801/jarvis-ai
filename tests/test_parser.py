import unittest

from core.parser import parse_decision


class ParserTests(unittest.TestCase):
    def test_new_tool_format(self):
        d = parse_decision('{"tool":"current_time","arguments":{}}')
        self.assertEqual(d.kind, "tool_call")
        self.assertEqual(d.tool_call.name, "current_time")

    def test_old_action_format_is_normalized(self):
        d = parse_decision(
            '{"action":"current_time","response":"2024-02-20 14:30:00"}'
        )
        self.assertEqual(d.kind, "tool_call")
        self.assertEqual(d.tool_call.name, "current_time")

    def test_fake_response_is_not_used_as_final(self):
        d = parse_decision(
            '{"action":"current_time","response":"2024-02-20 14:30:00"}'
        )
        self.assertNotEqual(d.kind, "final")

    def test_final_format(self):
        d = parse_decision('{"final":"Done."}')
        self.assertEqual(d.kind, "final")
        self.assertEqual(d.final_text, "Done.")


if __name__ == "__main__":
    unittest.main()

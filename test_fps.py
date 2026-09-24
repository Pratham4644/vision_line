import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("main", pathlib.Path(__file__).with_name("main.py"))
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


class FpsTests(unittest.TestCase):
    def test_calculate_fps(self):
        self.assertAlmostEqual(main.calculate_fps(10, 2.0), 5.0)

    def test_calculate_fps_handles_zero_time(self):
        self.assertEqual(main.calculate_fps(10, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()

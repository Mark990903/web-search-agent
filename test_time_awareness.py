from datetime import date
import unittest

from time_awareness import detect_time_range


class TimeAwarenessTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 6, 26)

    def test_detect_today(self):
        time_range = detect_time_range("今天 OpenAI 有什么新闻", self.today)

        self.assertEqual(time_range.start_date, date(2026, 6, 26))
        self.assertEqual(time_range.end_date, date(2026, 6, 26))

    def test_detect_recent(self):
        time_range = detect_time_range("最近 AI 搜索有什么变化", self.today)

        self.assertEqual(time_range.start_date, date(2026, 6, 20))
        self.assertEqual(time_range.end_date, date(2026, 6, 26))

    def test_detect_this_week(self):
        time_range = detect_time_range("本周新能源行业新闻", self.today)

        self.assertEqual(time_range.start_date, date(2026, 6, 22))
        self.assertEqual(time_range.end_date, date(2026, 6, 26))

    def test_detect_this_month(self):
        time_range = detect_time_range("这个月在ai领域有哪些新进展", self.today)

        self.assertEqual(time_range.label, "本月")
        self.assertEqual(time_range.start_date, date(2026, 6, 1))
        self.assertEqual(time_range.end_date, date(2026, 6, 26))

    def test_detect_this_month_english(self):
        time_range = detect_time_range("latest AI developments this month", self.today)

        self.assertEqual(time_range.label, "本月")
        self.assertEqual(time_range.start_date, date(2026, 6, 1))
        self.assertEqual(time_range.end_date, date(2026, 6, 26))

    def test_no_time_range(self):
        self.assertIsNone(detect_time_range("新能源汽车产业链分析", self.today))


if __name__ == "__main__":
    unittest.main()

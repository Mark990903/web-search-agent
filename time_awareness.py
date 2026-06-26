from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class TimeRange:
    """
    表示用户查询中识别出的时间范围。
    start_date 和 end_date 都是闭区间日期。
    """

    label: str
    start_date: date
    end_date: date

    @property
    def start_iso(self):
        return self.start_date.isoformat()

    @property
    def end_iso(self):
        return self.end_date.isoformat()

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

    def to_dict(self):
        return {
            "label": self.label,
            "start_date": self.start_iso,
            "end_date": self.end_iso,
            "days": self.days,
        }


def detect_time_range(query: str, today: date | None = None):
    """
    从用户 query 中识别常见相对时间表达。

    当前 v2.2 覆盖：
    - 今天 / 今日 / today
    - 最近 / 近期 / lately / recent / recently
    - 本周 / 这周 / this week
    - 本月 / 这个月 / this month
    """
    if today is None:
        today = datetime.now().date()

    normalized = query.lower()

    if any(keyword in normalized for keyword in ["今天", "今日", "today"]):
        return TimeRange("今天", today, today)

    if any(keyword in normalized for keyword in ["本周", "这周", "this week"]):
        start_of_week = today - timedelta(days=today.weekday())
        return TimeRange("本周", start_of_week, today)

    if any(keyword in normalized for keyword in ["本月", "这个月", "this month"]):
        start_of_month = today.replace(day=1)
        return TimeRange("本月", start_of_month, today)

    if any(keyword in normalized for keyword in ["最近", "近期", "recently", "recent", "lately"]):
        return TimeRange("最近7天", today - timedelta(days=6), today)

    return None


def describe_time_range(time_range: TimeRange | None):
    if not time_range:
        return "未识别到明确时间范围"

    return f"{time_range.label}（{time_range.start_iso} 至 {time_range.end_iso}）"

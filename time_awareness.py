from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class TimeRange:
    """Date range detected from a user query.

    Attributes:
        label: Human-readable range label.
        start_date: Inclusive start date.
        end_date: Inclusive end date.
    """

    label: str
    start_date: date
    end_date: date

    @property
    def start_iso(self) -> str:
        """Return the inclusive start date in ISO format."""
        return self.start_date.isoformat()

    @property
    def end_iso(self) -> str:
        """Return the inclusive end date in ISO format."""
        return self.end_date.isoformat()

    @property
    def days(self) -> int:
        """Return the inclusive day count for this range."""
        return (self.end_date - self.start_date).days + 1

    def to_dict(self) -> dict[str, str | int]:
        """Convert the time range into a Streamlit-friendly dictionary."""
        return {
            "label": self.label,
            "start_date": self.start_iso,
            "end_date": self.end_iso,
            "days": self.days,
        }


def detect_time_range(query: str, today: date | None = None) -> TimeRange | None:
    """Detect common relative time expressions in a query.

    Args:
        query: User query text.
        today: Optional fixed date for deterministic tests.

    Returns:
        A TimeRange when a supported expression is detected, otherwise None.
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

    if any(
        keyword in normalized
        for keyword in ["最近", "近期", "recently", "recent", "lately"]
    ):
        return TimeRange("最近7天", today - timedelta(days=6), today)

    return None


def describe_time_range(time_range: TimeRange | None) -> str:
    """Describe a detected time range for prompt context.

    Args:
        time_range: Optional detected TimeRange.

    Returns:
        Human-readable time range description.
    """
    if not time_range:
        return "未识别到明确时间范围"

    return f"{time_range.label}（{time_range.start_iso} 至 {time_range.end_iso}）"

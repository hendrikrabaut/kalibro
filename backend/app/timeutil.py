from datetime import UTC, datetime


def utc_naive(moment: datetime) -> datetime:
    """Stored form: naive UTC. Naive input is taken to be UTC already."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_utc(moment: datetime) -> datetime:
    """For output: mark stored naive UTC as UTC, so clients see '+00:00'."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment

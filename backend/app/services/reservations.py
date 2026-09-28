from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database_pool import db_pool


def empty_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": "0.00",
        "currency": "USD",
        "count": 0,
    }


def month_boundaries(year: int, month: int, property_timezone: str) -> tuple[datetime, datetime]:
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    start_local = datetime(year, month, 1, tzinfo=ZoneInfo(property_timezone))
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=ZoneInfo(property_timezone))
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=ZoneInfo(property_timezone))

    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    db_session=None,
) -> Decimal:
    summary = await calculate_total_revenue(
        property_id,
        tenant_id,
        month=month,
        year=year,
        db_session=db_session,
    )
    return Decimal(summary["total"])


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db_session=None,
) -> Dict[str, Any]:
    if (month is None) != (year is None):
        raise ValueError("month and year must be supplied together")

    if db_session is not None:
        return await _calculate_revenue(
            db_session, property_id, tenant_id, month, year
        )

    await db_pool.initialize()
    async with db_pool.get_session() as session:
        return await _calculate_revenue(session, property_id, tenant_id, month, year)


async def _calculate_revenue(
    session,
    property_id: str,
    tenant_id: str,
    month: Optional[int],
    year: Optional[int],
) -> Dict[str, Any]:
    property_result = await session.execute(
        text("""
            SELECT timezone
            FROM properties
            WHERE id = :property_id AND tenant_id = :tenant_id
        """),
        {"property_id": property_id, "tenant_id": tenant_id},
    )
    property_row = property_result.mappings().one_or_none()
    if property_row is None:
        return empty_revenue_summary(property_id, tenant_id)

    start_date = end_date = None
    if month is not None and year is not None:
        start_date, end_date = month_boundaries(year, month, property_row["timezone"])

    filters = [
        "property_id = :property_id",
        "tenant_id = :tenant_id",
    ]
    parameters = {"property_id": property_id, "tenant_id": tenant_id}
    if start_date is not None:
        filters.extend(
            [
                "check_in_date >= :start_date",
                "check_in_date < :end_date",
            ]
        )
        parameters["start_date"] = start_date
        parameters["end_date"] = end_date

    result = await session.execute(
        text(f"""
            SELECT
                COALESCE(SUM(total_amount), 0) AS total_revenue,
                COUNT(*) AS reservation_count,
                COALESCE(MIN(currency), 'USD') AS currency
            FROM reservations
            WHERE {' AND '.join(filters)}
        """),
        parameters,
    )
    row = result.mappings().one()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(Decimal(str(row["total_revenue"]))),
        "currency": row["currency"],
        "count": row["reservation_count"],
    }

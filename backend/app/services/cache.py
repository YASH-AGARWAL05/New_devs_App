import json
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def revenue_cache_key(
    property_id: str, tenant_id: str, month: Optional[int], year: Optional[int]
) -> str:
    period = "all" if month is None else f"{year}-{month:02d}"
    return f"revenue:{tenant_id}:{property_id}:{period}"


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch a tenant- and reporting-period-scoped revenue summary."""
    if (month is None) != (year is None):
        raise ValueError("month and year must be supplied together")

    cache_key = revenue_cache_key(property_id, tenant_id, month, year)
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    from app.services.reservations import calculate_total_revenue

    result = await calculate_total_revenue(property_id, tenant_id, month, year)
    await redis_client.setex(cache_key, 300, json.dumps(result))
    return result

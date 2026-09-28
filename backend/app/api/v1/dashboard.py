import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import authenticate_request as get_current_user
from app.services.cache import get_revenue_summary

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    if (month is None) != (year is None):
        raise HTTPException(
            status_code=422, detail="month and year must be supplied together"
        )

    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"
    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)
        total_revenue = Decimal(revenue_data["total"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except Exception as error:
        logger.exception("Unable to load dashboard revenue")
        raise HTTPException(status_code=500, detail="Unable to load dashboard revenue") from error

    return {
        "property_id": revenue_data["property_id"],
        "total_revenue": format(total_revenue, ".2f"),
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }

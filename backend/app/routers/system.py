from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_wms_token
from app.services import scan_timeouts


router = APIRouter(
    prefix="/system", tags=["system"], dependencies=[Depends(require_wms_token)]
)


@router.post("/timeouts/scan")
async def trigger_timeout_scan(session: AsyncSession = Depends(get_db)):
    return {"alerts": await scan_timeouts(session)}

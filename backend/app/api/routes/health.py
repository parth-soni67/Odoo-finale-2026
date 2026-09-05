from typing import Any, Dict
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(
    response: Response,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Basic service health check including database connection validation."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unavailable: {str(e)}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "version": settings.VERSION,
        "database": db_status
    }

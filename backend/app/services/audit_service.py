import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        entity_type: str,
        entity_id: int,
        action: str,
        user_id: Optional[int] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
    ) -> AuditLog:
        """Records an auditable mutation event in the persistent database."""
        old_val_str = (
            json.dumps(old_value, default=str)
            if isinstance(old_value, (dict, list))
            else (str(old_value) if old_value is not None else None)
        )
        new_val_str = (
            json.dumps(new_value, default=str)
            if isinstance(new_value, (dict, list))
            else (str(new_value) if new_value is not None else None)
        )

        log_entry = AuditLog(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_val_str,
            new_value=new_val_str,
        )
        db.add(log_entry)
        db.flush()
        return log_entry


audit_service = AuditService()

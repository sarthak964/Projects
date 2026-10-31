from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.time import utcnow
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import MarkAllReadOut, NotificationList, NotificationOut, UnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    total = query.count()
    rows = query.order_by(Notification.id.desc()).offset(offset).limit(limit).all()
    return NotificationList(
        items=[NotificationOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).count()
    return UnreadCount(unread_count=count)


@router.post("/read-all", response_model=MarkAllReadOut)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.execute(
        update(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        ).values(is_read=True, read_at=utcnow()).execution_options(synchronize_session=False)
    )
    db.commit()
    return MarkAllReadOut(marked_read=result.rowcount)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.execute(
        update(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        ).values(is_read=True, read_at=utcnow()).execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(row)
    return row

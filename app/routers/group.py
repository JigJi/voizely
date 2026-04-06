from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transcription import TranscriptionGroup, Transcription

router = APIRouter(tags=["groups"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/api/groups")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(TranscriptionGroup).order_by(TranscriptionGroup.sort_order).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "custom_instructions": g.custom_instructions,
            "is_default": g.is_default,
            "count": len(g.transcriptions),
        }
        for g in groups
    ]


@router.post("/api/groups")
async def create_group(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing name")
    max_order = db.query(TranscriptionGroup).count()
    group = TranscriptionGroup(name=name, sort_order=max_order, custom_instructions=body.get("custom_instructions"))
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"ok": True, "id": group.id}


@router.put("/api/groups/{group_id}")
async def update_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Not found")
    if "name" in body:
        group.name = body["name"].strip()
    if "custom_instructions" in body:
        group.custom_instructions = body["custom_instructions"].strip() or None
    db.commit()
    return {"ok": True}


@router.delete("/api/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Not found")
    if group.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default group")
    # Move transcriptions to default group
    default = db.query(TranscriptionGroup).filter(TranscriptionGroup.is_default == True).first()
    for t in group.transcriptions:
        t.group_id = default.id if default else None
    db.delete(group)
    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/assign-group")
async def assign_group(transcription_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    group_id = body.get("group_id")
    t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    t.group_id = group_id
    db.commit()
    return {"ok": True}

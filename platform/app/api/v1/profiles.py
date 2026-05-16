"""
Profile utilities — parse-only helpers exposed for the frontend.

The actual matching is done by /recommendations; this router lets the UI
preview a parsed CV before requesting recommendations.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.profile import ProfilePayload
from app.services.cv_parser import parse_cv

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/parse-cv", response_model=ProfilePayload)
async def parse_cv_preview(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=400, detail="Unsupported file type")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return parse_cv(file.filename or "cv", data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not parse CV: {e}")

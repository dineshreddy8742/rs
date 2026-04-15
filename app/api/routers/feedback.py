from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.database.models.feedback import Feedback, FeedbackCreate, FeedbackUpdate
from app.database.repositories.feedback_repository import FeedbackRepository
from app.api.routers.auth import get_current_user
from app.database.models.user import User as UserSchema

router = APIRouter(prefix="/feedback", tags=["feedback"])
repo = FeedbackRepository()

@router.post("/", response_model=str)
async def create_new_feedback(
    feedback_in: FeedbackCreate,
    current_user: UserSchema = Depends(get_current_user)
):
    """Submit new feedback, issue, or bug report."""
    feedback = Feedback(
        user_id=str(current_user.id),
        user_name=current_user.name,
        user_email=current_user.email,
        type=feedback_in.type,
        title=feedback_in.title,
        content=feedback_in.content,
        image=feedback_in.image
    )
    return await repo.create_feedback(feedback)

@router.get("/mine", response_model=List[Feedback])
async def get_my_feedback(current_user: UserSchema = Depends(get_current_user)):
    """Retrieve all feedback submitted by the current user."""
    items = await repo.get_feedback_by_user_id(str(current_user.id))
    return [Feedback(**item) for item in items]

@router.get("/admin/all", response_model=List[Feedback])
async def get_all_feedback_for_admin(current_user: UserSchema = Depends(get_current_user)):
    """Retrieve all system feedback (Admin only)."""
    if not current_user.is_admin and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    items = await repo.get_all_feedback()
    return [Feedback(**item) for item in items]

@router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    update_data: FeedbackUpdate,
    current_user: UserSchema = Depends(get_current_user)
):
    """Update existing feedback (Owner or Admin)."""
    existing = await repo.get_feedback_by_id(feedback_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check ownership or admin status
    if existing["user_id"] != str(current_user.id) and not current_user.is_admin and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    data = update_data.model_dump(exclude_unset=True)
    success = await repo.update_feedback(feedback_id, data)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"message": "Updated successfully"}

@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    current_user: UserSchema = Depends(get_current_user)
):
    """Delete feedback (Owner or Admin)."""
    existing = await repo.get_feedback_by_id(feedback_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    if existing["user_id"] != str(current_user.id) and not current_user.is_admin and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    success = await repo.delete_feedback(feedback_id)
    if not success:
        raise HTTPException(status_code=400, detail="Deletion failed")
    return {"message": "Deleted successfully"}

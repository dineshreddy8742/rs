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
    user_id: str = Depends(get_current_user)
):
    """Submit new feedback, issue, or bug report."""
    from app.database.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    current_user = await user_repo.get_user_by_id(user_id)
    
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    feedback = Feedback(
        user_id=user_id,
        user_name=current_user.get("name", "Anonymous"),
        user_email=current_user.get("email"),
        type=feedback_in.type,
        title=feedback_in.title,
        content=feedback_in.content,
        image=feedback_in.image
    )
    res_id, error = await repo.create_feedback(feedback)
    if not res_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database Error: {error or 'Unknown failure during submission'}"
        )
    return res_id

@router.get("/mine", response_model=List[Feedback])
async def get_my_feedback(user_id: str = Depends(get_current_user)):
    """Retrieve all feedback submitted by the current user."""
    items = await repo.get_feedback_by_user_id(user_id)
    return [Feedback(**item) for item in items]

@router.get("/admin/all", response_model=List[Feedback])
async def get_all_feedback_for_admin(user_id: str = Depends(get_current_user)):
    """Retrieve all system feedback (Admin only)."""
    from app.database.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    current_user = await user_repo.get_user_by_id(user_id)
    
    if not current_user or (not current_user.get("is_admin", False) and current_user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    items = await repo.get_all_feedback()
    return [Feedback(**item) for item in items]

@router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    update_data: FeedbackUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update existing feedback (Owner or Admin)."""
    from app.database.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    current_user = await user_repo.get_user_by_id(user_id)
    
    existing = await repo.get_feedback_by_id(feedback_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check ownership or admin status
    is_admin = current_user and (current_user.get("is_admin", False) or current_user.get("role") == "admin")
    if existing["user_id"] != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    data = update_data.model_dump(exclude_unset=True)
    success = await repo.update_feedback(feedback_id, data)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"message": "Updated successfully"}

@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete feedback (Owner or Admin)."""
    from app.database.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    current_user = await user_repo.get_user_by_id(user_id)
    
    existing = await repo.get_feedback_by_id(feedback_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    is_admin = current_user and (current_user.get("is_admin", False) or current_user.get("role") == "admin")
    if existing["user_id"] != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    success = await repo.delete_feedback(feedback_id)
    if not success:
        raise HTTPException(status_code=400, detail="Deletion failed")
    return {"message": "Deleted successfully"}

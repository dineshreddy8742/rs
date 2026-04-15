"""Feedback API router module for user reviews and feedback thread management."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.database.models.feedback import (
    Feedback, FeedbackCreate, FeedbackUpdate, 
    FeedbackMessage, FeedbackMessageAdd
)
from app.database.repositories.feedback_repository import FeedbackRepository
from app.core.security import get_current_user
from app.database.models.user import UserResponse
from app.database.repositories.user_repository import UserRepository

feedback_router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

async def get_feedback_repo():
    return FeedbackRepository()

@feedback_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    feedback_in: FeedbackCreate,
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Create a new feedback thread."""
    message = FeedbackMessage(
        sender_id=current_user.id,
        sender_role=current_user.role,
        content=feedback_in.content
    )
    
    new_feedback = Feedback(
        user_id=current_user.id,
        user_name=current_user.name,
        user_email=current_user.email,
        subject=feedback_in.subject,
        rating=feedback_in.rating,
        messages=[message],
        is_public=feedback_in.is_public
    )
    
    feedback_id = await repo.create_feedback(new_feedback)
    if not feedback_id:
        raise HTTPException(status_code=500, detail="Failed to save feedback")
        
    return {"id": feedback_id, "message": "Feedback submitted successfully"}

@feedback_router.get("/mine", response_model=List[Feedback])
async def get_my_feedback(
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Get all feedback threads for the current user."""
    return await repo.get_user_feedback(current_user.id)

@feedback_router.get("/unread-count")
async def get_unread_count(
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Get count of unread messages for the current user."""
    feedback_list = await repo.get_user_feedback(current_user.id)
    count = 0
    for fb in feedback_list:
        messages = fb.get("messages", [])
        for msg in messages:
            if msg.get("sender_role") != current_user.role and not msg.get("is_read"):
                count += 1
    return {"count": count}

@feedback_router.post("/{feedback_id}/read")
async def mark_feedback_as_read(
    feedback_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Mark all messages in a thread as read by the current user."""
    success = await repo.mark_messages_as_read(feedback_id, current_user.role)
    return {"success": success}

@feedback_router.get("/all", response_model=List[Feedback])
async def get_all_feedback(
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Get all feedback threads (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await repo.get_all_feedback()

@feedback_router.get("/admin/unread-count")
async def get_admin_unread_count(
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Get count of threads with unread student messages (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    all_fb = await repo.get_all_feedback()
    count = 0
    for fb in all_fb:
        messages = fb.get("messages", [])
        if not messages:
            continue
        # Check if any student message is unread
        has_unread = any(m.get("sender_role") != "admin" and not m.get("is_read") for m in messages)
        if has_unread:
            count += 1
    return {"count": count}

@feedback_router.post("/{feedback_id}/message")
async def add_feedback_message(
    feedback_id: str,
    message_in: FeedbackMessageAdd,
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Add a message to a feedback thread."""
    feedback = await repo.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    # Only owner or admin can add messages
    if feedback["user_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    message = FeedbackMessage(
        sender_id=current_user.id,
        sender_role=current_user.role,
        content=message_in.content
    )
    
    success = await repo.add_message(feedback_id, message)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add message")
        
    return {"message": "Message added successfully"}

@feedback_router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    update_in: FeedbackUpdate,
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Update feedback metadata (owner can update rating/subject, admin can update status)."""
    feedback = await repo.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    if feedback["user_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    update_data = update_in.model_dump(exclude_unset=True)
    
    # Restrict status updates to admins
    if "status" in update_data and not current_user.is_admin:
        del update_data["status"]
        
    success = await repo.update_feedback(feedback_id, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update feedback")
        
    return {"message": "Feedback updated successfully"}

@feedback_router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    current_user: UserResponse = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo)
):
    """Delete feedback (Owner only)."""
    feedback = await repo.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    if feedback["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this feedback")
        
    success = await repo.delete_feedback(feedback_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete feedback")
        
    return {"message": "Feedback deleted successfully"}

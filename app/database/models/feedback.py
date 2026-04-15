"""Feedback data model for user reviews and suggestions."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FeedbackMessage(BaseModel):
    """A single message in a feedback thread."""
    sender_id: str = Field(..., description="ID of the user who sent this message")
    sender_role: str = Field(..., description="Role of the sender (student, admin, etc.)")
    content: str = Field(..., description="Content of the message")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_read: bool = Field(default=False, description="Whether the recipient has read this message")


class Feedback(BaseModel):
    """User feedback model for college resume builder."""
    id: Optional[str] = None
    user_id: str = Field(..., description="ID of the user who initiated the feedback")
    user_name: str = Field(..., description="Name of the user")
    user_email: str = Field(..., description="Email of the user")
    subject: str = Field(default="User Feedback", description="Subject of the feedback")
    rating: int = Field(default=5, ge=1, le=5, description="Star rating (1-5)")
    status: str = Field(default="open", description="Status (open, in-progress, resolved, closed)")
    messages: List[FeedbackMessage] = Field(default_factory=list, description="Chat messages thread")
    is_public: bool = Field(default=False, description="Whether this feedback can be shown publicly as a review")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class FeedbackCreate(BaseModel):
    """Request model for creating new feedback."""
    subject: Optional[str] = "User Feedback"
    rating: int = Field(5, ge=1, le=5)
    content: str = Field(..., min_length=1)
    is_public: bool = False


class FeedbackUpdate(BaseModel):
    """Request model for updating feedback content or status."""
    subject: Optional[str] = None
    rating: Optional[int] = None
    status: Optional[str] = None
    is_public: Optional[bool] = None


class FeedbackMessageAdd(BaseModel):
    """Request model for adding a message to a feedback thread."""
    content: str = Field(..., min_length=1)

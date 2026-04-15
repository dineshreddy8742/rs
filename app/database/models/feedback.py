from datetime import datetime
from typing import Optional
from pydantic import Field
from app.database.models.base import BaseSchema

class Feedback(BaseSchema):
    """Model representing user feedback, bugs, or suggestions."""
    id: Optional[str] = None
    user_id: str
    user_name: Optional[str] = "Anonymous"
    user_email: Optional[str] = None
    
    type: str = "general" # bug, suggestion, general, issue
    title: str
    content: str
    image: Optional[str] = None # Base64 encoded image
    
    status: str = "pending" # pending, reviewed, resolved, ignored
    admin_response: Optional[str] = None
    is_public: bool = False
    
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class FeedbackCreate(BaseSchema):
    type: str = "general"
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=2)
    image: Optional[str] = None

class FeedbackUpdate(BaseSchema):
    type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    status: Optional[str] = None
    admin_response: Optional[str] = None

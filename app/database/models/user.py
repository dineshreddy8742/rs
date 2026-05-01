"""User data model for authentication and authorization."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """User model for college resume builder authentication."""
    id: Optional[str] = None
    email: str = Field(..., description="User email (unique)")
    roll_number: str = Field(..., description="Student roll number (unique)")
    name: str = Field(..., description="Student full name")
    college: str = Field(..., description="College/institution name")
    role: str = Field(default="student", description="User role (student, employee, admin)")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    is_active: bool = True
    is_admin: bool = False
    resume_count: int = 0
    daily_limit: int = 5
    monthly_limit: int = 50
    yearly_limit: int = 500
    last_login: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class UserCreate(BaseModel):
    """Request model for user registration."""
    email: str = Field(..., min_length=5, max_length=100)
    roll_number: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    college: str = Field(..., min_length=2, max_length=200)
    role: str = Field(default="student", min_length=2, max_length=20)
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """Request model for user login."""
    email: str
    password: str
    role: str = "student"


class UserResponse(BaseModel):
    """Response model (excludes password)."""
    id: Optional[str] = None
    email: str
    roll_number: str
    name: str
    college: str
    role: str
    is_active: bool
    is_admin: bool
    resume_count: int
    daily_limit: int
    monthly_limit: int
    yearly_limit: int
    last_login: Optional[str] = None
    created_at: str


class AdminStats(BaseModel):
    """Admin dashboard statistics."""
    total_users: int
    total_resumes: int
    colleges: list
    recent_logins: list
    users_by_college: dict

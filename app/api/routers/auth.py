"""Authentication API router - Login, Register, Admin."""

from datetime import timedelta
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.database.repositories.user_repository import UserRepository
from app.database.repositories.resume_repository import ResumeRepository
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_user_optional,
    ACCESS_TOKEN_EXPIRE_DAYS,
)

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


# ===== Profile Management =====
class ProfileUpdate(BaseModel):
    name: str
    college: str

class PasswordChange(BaseModel):
    current: str
    new: str

@auth_router.post("/update-profile")
async def update_profile(req: ProfileUpdate, user_id: str = Depends(get_current_user)):
    """Update user profile (name, college)."""
    repo = UserRepository()
    success = await repo.update_user(user_id, {"name": req.name, "college": req.college})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    user = await repo.get_user_by_id(user_id)
    user.pop("password_hash", None)
    return user


@auth_router.post("/change-password")
async def change_password(req: PasswordChange, user_id: str = Depends(get_current_user)):
    """Change user password."""
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not verify_password(req.current, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    if len(req.new) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    success = await repo.update_user(user_id, {"password_hash": hash_password(req.new)})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to change password")
    
    return {"success": True, "message": "Password changed successfully"}


@auth_router.post("/delete-account")
async def delete_account(user_id: str = Depends(get_current_user)):
    """Delete user account and all associated data."""
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete user's resumes first
    resume_repo = ResumeRepository()
    user_resumes = await resume_repo.get_resumes_by_user_id(user_id)
    for resume in user_resumes:
        await resume_repo.delete_resume(resume.get("id"))
    
    # Delete user
    success = await repo.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete account")
    
    return {"success": True, "message": "Account deleted successfully"}


# ===== Registration =====
class RegisterRequest(BaseModel):
    email: str
    roll_number: str
    name: str
    college: str
    role: str = "student"
    password: str

class RegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None

@auth_router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, response: Response):
    """Register a new student/employee account."""
    repo = UserRepository()
    
    # Check if email already exists
    existing_email = await repo.get_user_by_email(req.email.lower())
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered. Please login instead.")

    # Check if roll number already exists
    existing = await repo.get_user_by_roll_number(req.roll_number.lower())
    if existing:
        raise HTTPException(status_code=400, detail="Roll number already registered. Please login instead.")
    
    # Create user
    user_data = {
        "email": req.email.lower(),
        "roll_number": req.roll_number.lower(),
        "name": req.name,
        "college": req.college,
        "role": req.role,
        "password_hash": hash_password(req.password),
    }
    
    user_id = await repo.create_user(user_data)
    if not user_id:
        raise HTTPException(status_code=500, detail="Failed to create account. Try again.")
    
    # Auto-login after registration
    access_token = create_access_token(
        data={"sub": user_id, "email": req.email.lower()},
        expires_delta=timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    )
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    
    return RegisterResponse(success=True, message="Account created successfully!", user_id=user_id)


# ===== Login =====
class LoginRequest(BaseModel):
    email: Optional[str] = None
    roll_number: Optional[str] = None
    password: str
    role: str = "student"

class LoginResponse(BaseModel):
    success: bool
    message: str
    name: str = ""
    college: str = ""
    role: str = "student"
    is_admin: bool = False

@auth_router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response):
    """Login using Supabase Auth."""
    # Accept either email or roll_number
    identifier = req.email or req.roll_number
    if not identifier:
        raise HTTPException(status_code=400, detail="Email or roll number required.")

    repo = UserRepository()
    client = repo.connection_manager.get_client()

    try:
        # Try to find user by email or roll_number
        user = None
        email = None
        
        # Check if input looks like an email (contains @)
        if '@' in identifier:
            user = await repo.get_user_by_email(identifier.lower())
            email = identifier.lower()
            print(f"DEBUG: Looking up by EMAIL: {identifier}")
        else:
            # Try roll_number lookup
            user = await repo.get_user_by_roll_number(identifier.lower())
            email = user.get("email") if user else None
            print(f"DEBUG: Looking up by ROLL_NUMBER: {identifier}")
        
        print(f"DEBUG LOGIN ATTEMPT: identifier={identifier}, user_found={user is not None}")
        if user:
            print(f"DEBUG USER: id={user.get('id')}, roll={user.get('roll_number')}, has_password={bool(user.get('password_hash'))}, is_active={user.get('is_active')}")
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found. Contact admin to create account.")
        
        # Check password hash
        from app.core.security import verify_password
        
        stored_hash = user.get("password_hash")
        password_valid = stored_hash and verify_password(req.password, stored_hash)
        print(f"DEBUG PASSWORD: stored={bool(stored_hash)}, valid={password_valid}")
        
        if not stored_hash or not verify_password(req.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid password.")
        
        print(f"DEBUG STATUS: is_active={user.get('is_active')}")
        # Check user status
        if not user.get("is_active", False):
            raise HTTPException(status_code=403, detail="Account pending approval. Contact admin.")

        # 4. Strict Role Verification
        if user.get("role") != req.role:
            raise HTTPException(status_code=403, detail=f"Access denied for role: {req.role}")

        if user.get("status") == "blocked":
            raise HTTPException(status_code=403, detail="Your account has been blocked.")

        # 5. Set Session Cookie
        response.set_cookie(
            key="auth_token",
            value=create_access_token(data={"sub": str(user.get("id", "")), "role": user.get("role", "student")}),
            httponly=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        print(f"DEBUG: Cookie set with user_id={user.get('id')}, role={user.get('role')}")

        return LoginResponse(
            success=True,
            message="Login successful!",
            name=user.get("name", ""),
            college=user.get("college", ""),
            role=user.get("role", "student"),
            is_admin=user.get("is_admin", False) or user.get("role") == "admin"
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        raise HTTPException(status_code=400, detail=f"Login failed: {error_msg}")


# ===== Logout =====
@auth_router.post("/logout")
async def logout(response: Response):
    """Logout and clear session."""
    response.delete_cookie(key="auth_token")
    return {"success": True, "message": "Logged out successfully"}


# ===== Get Current User =====
@auth_router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    """Get current logged-in user info."""
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove password from response
    user.pop("password_hash", None)
    return user


# ===== Get User's Resumes =====
@auth_router.get("/my-resumes")
async def get_my_resumes(user_id: str = Depends(get_current_user)):
    """Get all resumes for the current user."""
    repo = ResumeRepository()
    resumes = await repo.get_resumes_by_user_id(user_id)
    return resumes


# ===== Admin Endpoints =====
class AdminStats(BaseModel):
    total_users: int
    total_resumes: int
    colleges: list
    users_by_college: dict
    recent_logins: list

@auth_router.get("/admin/stats")
async def get_admin_stats(user_id: str = Depends(get_current_user)):
    """Get statistics for admin dashboard (admin only)."""
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user or (not user.get("is_admin", False) and user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        stats = await repo.get_admin_stats()

        # Ensure colleges list is fetched correctly
        colleges_result = repo._get_supabase_client().table("colleges").select("name").execute()
        stats["colleges"] = [c["name"] for c in colleges_result.data] if colleges_result.data else []

        # Calculate total resumes safely
        users = await repo.get_all_users()
        stats["total_users"] = len(users)
        stats["total_resumes"] = sum(u.get("resume_count", 0) for u in users)

        return stats
    except Exception as e:
        print(f"Error fetching admin stats: {e}")
        return {
            "total_users": 0,
            "total_resumes": 0,
            "colleges": [],
            "users_by_college": {},
            "recent_logins": []
        }



@auth_router.get("/admin/users")
async def get_all_users(user_id: str = Depends(get_current_user)):
    """Get all registered users (admin only)."""
    repo = UserRepository()
    user = await repo.get_user_by_id(user_id)
    if not user or (not user.get("is_admin", False) and user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await repo.get_all_users()
    # Remove passwords
    for u in users:
        u.pop("password_hash", None)
    return users

@auth_router.post("/admin/add-user")
async def admin_add_user(req: RegisterRequest, user_id: str = Depends(get_current_user)):
    """Admin manually adds a user."""
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if email exists
    existing = await repo.get_user_by_email(req.email.lower())
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user_data = {
        "email": req.email.lower(),
        "roll_number": req.roll_number.lower(),
        "name": req.name,
        "college": req.college,
        "role": req.role,
        "password_hash": hash_password(req.password),
    }
    
    new_id = await repo.create_user(user_data)
    return {"success": True, "user_id": new_id}

@auth_router.post("/admin/bulk-import")
async def admin_bulk_import(users: List[RegisterRequest], user_id: str = Depends(get_current_user)):
    """Admin bulk imports users from CSV data sent from frontend."""
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users_to_add = []
    for u in users:
        users_to_add.append({
            "email": u.email.lower(),
            "roll_number": u.roll_number.lower(),
            "name": u.name,
            "college": u.college,
            "role": u.role,
            "password_hash": hash_password(u.password),
            "is_active": True,
            "is_admin": False
        })
    
    result = repo._get_table().insert(users_to_add).execute()
    return {"success": True, "count": len(result.data) if result.data else 0}


# ===== College Management Models =====
class CollegeCreate(BaseModel):
    name: str
    email: str

class CollegeUpdate(BaseModel):
    name: str
    email: str

# ===== College Management =====

@auth_router.get("/admin/colleges")
async def get_colleges(user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = repo._get_supabase_client().table("colleges").select("*").execute()
    return result.data

@auth_router.post("/admin/colleges")
async def add_college(req: CollegeCreate, user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = repo._get_supabase_client().table("colleges").insert({"name": req.name, "email": req.email}).execute()
    if result.data:
        return result.data[0]
    return {"name": req.name, "email": req.email, "success": True}

@auth_router.put("/admin/colleges/{college_id}")
async def update_college(college_id: str, req: CollegeUpdate, user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = repo._get_supabase_client().table("colleges").update({"name": req.name, "email": req.email}).eq("id", college_id).execute()
    if result.data:
        return result.data[0]
    raise HTTPException(status_code=404, detail="College not found")

@auth_router.delete("/admin/colleges/{college_id}")
async def delete_college(college_id: str, user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    # Check if college info exists to get the name
    college_res = repo._get_supabase_client().table("colleges").select("name").eq("id", college_id).execute()
    if not college_res.data:
        raise HTTPException(status_code=404, detail="College not found")
    
    college_name = college_res.data[0].get("name")

    # Check if college has students (by name)
    students = repo._get_supabase_client().table("users").select("id").eq("college", college_name).execute()
    if students.data and len(students.data) > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete college with {len(students.data)} enrolled students. Remove students first.")

    result = repo._get_supabase_client().table("colleges").delete().eq("id", college_id).execute()
    return {"success": True, "message": "College deleted successfully"}

@auth_router.get("/admin/colleges/{college_id}/details")
async def get_college_details(college_id: str, user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get college info
    college_result = repo._get_supabase_client().table("colleges").select("*").eq("id", college_id).execute()
    if not college_result.data:
        raise HTTPException(status_code=404, detail="College not found")
    
    college = college_result.data[0]
    
    # Get students from this college
    students = repo._get_supabase_client().table("users").select("id, name, email, roll_number, is_active, resume_count, created_at").eq("college", college.get("name", "")).execute()
    
    college["students"] = students.data or []
    college["total_students"] = len(college["students"])
    college["total_resumes"] = sum(s.get("resume_count", 0) for s in college["students"])
    
    return college

# ===== User Status Control =====

@auth_router.post("/admin/users/{target_id}/status")
async def update_user_status(target_id: str, status: str, user_id: str = Depends(get_current_user)):
    """Set user status to 'approved', 'pending', or 'blocked'."""
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # If blocking, also set is_active to false
    is_active = status != "blocked"

    success = await repo.update_user(target_id, {"status": status, "is_active": is_active})
    return {"success": success}

@auth_router.delete("/admin/users/{target_id}")
async def delete_user(target_id: str, user_id: str = Depends(get_current_user)):
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    success = await repo.delete_user(target_id)
    return {"success": success}



@auth_router.post("/admin/disable-user")
async def disable_user(target_user_id: str, user_id: str = Depends(get_current_user)):
    """Disable a user account."""
    repo = UserRepository()
    requester = await repo.get_user_by_id(user_id)
    if not requester or (not requester.get("is_admin", False) and requester.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await repo.update_user(target_user_id, {"is_active": False})
    return {"success": True, "message": "User disabled"}


@auth_router.post("/admin/enable-user")
async def enable_user(target_user_id: str, user_id: str = Depends(get_current_user)):
    """Enable a disabled user account."""
    repo = UserRepository()
    requester = await repo.get_user_by_id(user_id)
    if not requester or (not requester.get("is_admin", False) and requester.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await repo.update_user(target_user_id, {"is_active": True})
    return {"success": True, "message": "User enabled"}


class AdminUserUpdate(BaseModel):
    id: str
    name: str
    college: str
    is_admin: bool = False
    is_active: bool = True

@auth_router.post("/admin/update-user")
async def admin_update_user(req: AdminUserUpdate, user_id: str = Depends(get_current_user)):
    """Admin update any user's profile."""
    repo = UserRepository()
    requester = await repo.get_user_by_id(user_id)
    if not requester or (not requester.get("is_admin", False) and requester.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {
        "name": req.name,
        "college": req.college,
        "is_admin": req.is_admin,
        "is_active": req.is_active,
    }
    
    success = await repo.update_user(req.id, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")
    
    return {"success": True, "message": "User updated successfully"}

@auth_router.get("/admin/activity")
async def get_recent_activity(user_id: str = Depends(get_current_user)):
    """Get 10 most recent user registrations."""
    repo = UserRepository()
    admin = await repo.get_user_by_id(user_id)
    if not admin or (not admin.get("is_admin", False) and admin.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = repo._get_supabase_client().table("users").select("id, name, email, college, created_at").order("created_at", desc=True).limit(10).execute()
    return result.data or []

"""
Database Schemas

University app collections using Pydantic models.
Each model name maps to a MongoDB collection with the lowercase class name.

Example:
- User -> "user"
- Course -> "course"
- Enrollment -> "enrollment"
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class User(BaseModel):
    """Users collection schema"""
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field("student", description="Role: student or admin")
    is_active: bool = Field(True, description="Whether user is active")


class Course(BaseModel):
    """Courses collection schema"""
    code: str = Field(..., description="Course code, e.g., CS101")
    title: str = Field(..., description="Course title")
    description: Optional[str] = Field(None, description="Brief description")
    credits: int = Field(3, ge=0, le=10, description="Credit hours")
    instructor: str = Field(..., description="Instructor name")
    tags: List[str] = Field(default_factory=list, description="Tags for search")


class Enrollment(BaseModel):
    """Enrollments collection schema"""
    user_id: str = Field(..., description="User ObjectId as string")
    course_id: str = Field(..., description="Course ObjectId as string")
    status: str = Field("enrolled", description="enrolled | dropped | completed")
    enrolled_at: Optional[datetime] = Field(default=None, description="Enrollment time")

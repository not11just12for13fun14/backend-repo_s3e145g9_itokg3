import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Course, Enrollment

app = FastAPI(title="University API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "University API is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# ---------- Auth & Accounts (basic) ----------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# NOTE: For demo purposes we store a hashed password using a simple method.
# In production use passlib/bcrypt and JWT. Here we avoid extra deps.
import hashlib

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

@app.post("/auth/register")
def register(payload: RegisterRequest):
    # Check if user exists
    existing = db["user"].find_one({"email": payload.email}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="student",
        is_active=True,
    )
    user_id = create_document("user", user)
    return {"id": user_id, "name": user.name, "email": user.email, "role": user.role}

@app.post("/auth/login")
def login(payload: LoginRequest):
    doc = db["user"].find_one({"email": payload.email}) if db else None
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if doc.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Return a simple session token (NOT secure, demo only)
    token = hashlib.sha1(f"{doc['_id']}{payload.email}".encode()).hexdigest()
    return {"token": token, "user": {"id": str(doc["_id"]), "name": doc["name"], "email": doc["email"], "role": doc.get("role", "student")}}

# ---------- Courses ----------
class CourseRequest(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    credits: int = 3
    instructor: str
    tags: Optional[List[str]] = None

@app.post("/courses")
def create_course(payload: CourseRequest):
    # Basic uniqueness on code
    existing = db["course"].find_one({"code": payload.code}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Course code already exists")
    course = Course(
        code=payload.code,
        title=payload.title,
        description=payload.description,
        credits=payload.credits,
        instructor=payload.instructor,
        tags=payload.tags or [],
    )
    course_id = create_document("course", course)
    return {"id": course_id}

@app.get("/courses")
def list_courses(q: Optional[str] = None, tag: Optional[str] = None):
    filter_q = {}
    if q:
        filter_q["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"code": {"$regex": q, "$options": "i"}},
            {"instructor": {"$regex": q, "$options": "i"}},
        ]
    if tag:
        filter_q["tags"] = tag
    docs = get_documents("course", filter_q)
    return [
        {
            "id": str(d["_id"]),
            "code": d["code"],
            "title": d["title"],
            "description": d.get("description"),
            "credits": d.get("credits", 3),
            "instructor": d.get("instructor"),
            "tags": d.get("tags", []),
        }
        for d in docs
    ]

# ---------- Enrollment ----------
class EnrollRequest(BaseModel):
    user_id: str
    course_id: str

@app.post("/enroll")
def enroll(payload: EnrollRequest):
    # Basic checks
    if not ObjectId.is_valid(payload.user_id) or not ObjectId.is_valid(payload.course_id):
        raise HTTPException(status_code=400, detail="Invalid IDs")
    user = db["user"].find_one({"_id": ObjectId(payload.user_id)}) if db else None
    course = db["course"].find_one({"_id": ObjectId(payload.course_id)}) if db else None
    if not user or not course:
        raise HTTPException(status_code=404, detail="User or course not found")
    # Check existing
    existing = db["enrollment"].find_one({"user_id": payload.user_id, "course_id": payload.course_id}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled")
    enrollment = Enrollment(user_id=payload.user_id, course_id=payload.course_id)
    enroll_id = create_document("enrollment", enrollment)
    return {"id": enroll_id, "status": "enrolled"}

@app.get("/users/{user_id}/enrollments")
def list_user_enrollments(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    docs = get_documents("enrollment", {"user_id": user_id})
    # hydrate course info
    result = []
    for e in docs:
        c = db["course"].find_one({"_id": ObjectId(e["course_id"])}) if db else None
        if c:
            result.append({
                "enrollment_id": str(e["_id"]),
                "status": e.get("status", "enrolled"),
                "course": {
                    "id": str(c["_id"]),
                    "code": c["code"],
                    "title": c["title"],
                    "instructor": c.get("instructor"),
                    "credits": c.get("credits", 3)
                }
            })
    return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

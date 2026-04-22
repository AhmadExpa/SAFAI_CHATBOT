try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
    import os
    import json
except ImportError as e:
    print(f"❌ Import error in simple.py: {e}")
    # Create minimal fallback
    class FastAPI:
        def __init__(self, *args, **kwargs): pass
        def add_middleware(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): 
            def decorator(func): return func
            return decorator
        def post(self, *args, **kwargs): 
            def decorator(func): return func
            return decorator
    class HTTPException(Exception): pass
    class CORSMiddleware: pass
    class JSONResponse: pass
    class BaseModel: pass
    class ConfigDict(dict): pass
    def Field(*args, **kwargs): return None
    class AliasChoices:
        def __init__(self, *args, **kwargs): pass
    def model_validator(*args, **kwargs):
        def decorator(func): return func
        return decorator

# Create a simple FastAPI app for testing
app = FastAPI(title="PhatagiAI Backend", version="1.0.0")

# Add CORS middleware with more permissive settings
# Get allowed origins from environment variable, fallback to localhost for dev
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else []
if not cors_origins or cors_origins == [""]:
    # Default to localhost for development
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:3002", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Pydantic models for auth
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("username", "full_name", "fullName", "name"),
    )
    email: str
    password: str

    @model_validator(mode="after")
    def set_username(self):
        if self.username:
            self.username = self.username.strip()
            return self

        email_local_part = self.email.split("@", 1)[0]
        fallback_name = email_local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        self.username = fallback_name or self.email
        return self

@app.get("/")
async def root():
    return {"message": "PhatagiAI Backend is running!", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Backend is working"}

# Auth endpoints
@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        # Simple mock login for testing
        if request.email == "test@example.com" and request.password == "password":
            return {
                "access_token": "mock_token_12345",
                "token_type": "bearer",
                "user": {
                    "email": request.email,
                    "username": "testuser"
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Login failed: {str(e)}"}
        )

@app.post("/auth/register")
async def register(request: RegisterRequest):
    try:
        # Simple mock registration for testing
        return {
            "message": "User registered successfully",
            "user": {
                "username": request.username,
                "email": request.email
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Registration failed: {str(e)}"}
        )

# API endpoints
@app.get("/api/projects")
async def get_projects():
    return {"projects": [], "message": "Projects endpoint working"}

@app.get("/api/conversations")
async def get_conversations():
    return {"conversations": [], "message": "Conversations endpoint working"}

# Test endpoint for debugging
@app.get("/test")
async def test_endpoint():
    return {
        "message": "Backend is working!",
        "cors_working": True,
        "status": "healthy",
        "endpoints": ["/", "/health", "/auth/login", "/auth/register", "/api/projects", "/api/conversations", "/test"]
    }

@app.get("/status")
async def status_endpoint():
    return {
        "status": "healthy",
        "message": "Simple backend is running",
        "version": "1.0.0"
    }

# This is the ASGI application that Vercel will use
handler = app

# Ensure proper export for Vercel
print(f"✅ Simple app handler type: {type(handler)}")
print(f"✅ Simple app is ASGI: {hasattr(handler, 'asgi') if hasattr(handler, 'asgi') else 'No asgi attribute'}")

# Export for Vercel
__all__ = ['handler', 'app']

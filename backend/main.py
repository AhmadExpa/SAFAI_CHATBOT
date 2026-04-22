
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
from app.config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)



from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import secrets
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import routers with error handling to catch charmap errors
# Import routers with error handling
try:
    logger.info("🔍 Importing OpenAI router...")
    from app.routers.openai.openai_chat import router as openai_chat
    logger.info("✅ OpenAI router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing OpenAI router: {e}")
    raise

try:
    logger.info("🔍 Importing auth router...")
    from app.routers.auth import router as auth_router
    logger.info("✅ Auth router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing auth router: {e}")
    raise

try:
    logger.info("🔍 Importing conversations router...")
    from app.routers.conversations import router as conversations_router
    logger.info("✅ Conversations router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing conversations router: {e}")
    raise

try:
    logger.info("🔍 Importing projects router...")
    from app.routers.projects import router as projects_router
    logger.info("✅ Projects router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing projects router: {e}")
    raise

try:
    logger.info("🔍 Importing project files router...")
    from app.routers.project_files import router as project_files_router
    logger.info("✅ Project files router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing project files router: {e}")
    raise

try:
    logger.info("🔍 Importing enhanced projects router...")
    from app.routers.enhanced_projects import router as enhanced_projects_router
    logger.info("✅ Enhanced projects router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing enhanced projects router: {e}")
    raise

try:
    logger.info("🔍 Importing XAI router...")
    from app.routers.xai.xai_chat import xai_router
    logger.info("✅ XAI router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing XAI router: {e}")
    raise

try:
    logger.info("🔍 Importing Qwen router...")
    from app.routers.qwen.qwen_chat import qwen_router
    logger.info("✅ Qwen router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Qwen router: {e}")
    raise

try:
    logger.info("🔍 Importing Moonshot router...")
    from app.routers.moonshot.moonshot_chat import moonshot_router
    logger.info("✅ Moonshot router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Moonshot router: {e}")
    raise

try:
    logger.info("🔍 Importing Multi-Model router...")
    from app.routers.multi_model_chat import router as multi_model_router
    logger.info("✅ Multi-Model router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Multi-Model router: {e}")
    raise

try:
    logger.info("🔍 Importing Gemini router...")
    from app.routers.google.gemini_chat import router as gemini_router
    logger.info("✅ Gemini router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Gemini router: {e}")
    raise

try:
    logger.info("🔍 Importing Perplexity router...")
    from app.routers.perplexity.perplexity_chat import router as perplexity_router
    logger.info("✅ Perplexity router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Perplexity router: {e}")
    raise

try:
    logger.info("🔍 Importing Anthropic router...")
    from app.routers.anthropic.anthropic_chat import router as anthropic_router
    logger.info("✅ Anthropic router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Anthropic router: {e}")
    raise

try:
    logger.info("🔍 Importing Response Comments router...")
    from app.routers.response_comments import router as response_comments_router
    logger.info("✅ Response Comments router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Response Comments router: {e}")
    raise

try:
    logger.info("🔍 Importing Personalities router...")
    from app.routers.personalities import router as personalities_router
    logger.info("✅ Personalities router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Personalities router: {e}")
    raise

try:
    logger.info("🔍 Importing Workspaces router...")
    from app.routers.workspaces import router as workspaces_router
    logger.info("✅ Workspaces router imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing Workspaces router: {e}")
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    try:
        logger.info("🔍 Quick database check on startup...")
        from app.services.database import check_database_health
        
        # Skip slow connection tests during startup for faster Railway healthcheck
        # Database connections will be established on first use
        logger.info("✅ Database configured - connections will be established on demand")
        logger.info("✅ Server startup complete")
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        logger.warning("⚠️  Server will continue but database features may not work properly")
    
    yield
    
    # Shutdown
    try:
        from app.services.database import close_all_connections
        logger.info("🔍 Closing database connections...")
        await close_all_connections()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database connections: {e}")

app = FastAPI(lifespan=lifespan)

# --- MIDDLEWARE STACK ---

# 1. Custom 400 Handler to see why preflights fail
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    print(f"❌ 500 Internal Server Error on {request.method} {request.url}")
    print(f"❌ Error: {str(exc)}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500, 
        content={
            "detail": f"Internal Server Error: {str(exc)}",
            "type": type(exc).__name__,
            "traceback": traceback.format_exc() if os.getenv("DEBUG", "true").lower() == "true" else None
        }
    )

@app.exception_handler(400)
async def custom_400_handler(request: Request, exc: Exception):
    print(f"🔥 DEBUG: 400 Bad Request on {request.method} {request.url}")
    print(f"🔥 DEBUG: Headers: {dict(request.headers)}")
    return JSONResponse(status_code=400, content={"detail": "Bad Request Debug", "headers": dict(request.headers)})

# 3. CORS Middleware
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add origins from environment variable if available
env_origins = os.getenv("CORS_ALLOWED_ORIGINS")
if env_origins:
    allowed_origins.extend([origin.strip() for origin in env_origins.split(",")])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# 4. Session Middleware
session_secret = os.getenv("SESSION_SECRET_KEY")
if not session_secret and (os.getenv("RAILWAY_ENVIRONMENT") == "true" or os.getenv("RAILWAY_PROJECT_ID")):
    logger.critical("❌ SESSION_SECRET_KEY must be set in production!")
    raise ValueError("SESSION_SECRET_KEY must be set in production!")

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret or "development-secret-key"
)

logger.info("✅ Middleware stack configured")

# Include routers
app.include_router(openai_chat, prefix="/openai", tags=["openai"])
app.include_router(xai_router, prefix="/xai", tags=["xai"])
app.include_router(qwen_router, prefix="/qwen", tags=["qwen"])
app.include_router(moonshot_router, prefix="/moonshot", tags=["moonshot"])
app.include_router(multi_model_router, prefix="/api", tags=["multi-model"])
app.include_router(gemini_router, prefix="/gemini", tags=["gemini"])
app.include_router(perplexity_router, prefix="/perplexity", tags=["perplexity"])
app.include_router(anthropic_router, prefix="/anthropic", tags=["anthropic"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(projects_router, prefix="/api", tags=["projects"])
app.include_router(project_files_router, prefix="/api", tags=["project-files"])
app.include_router(response_comments_router, prefix="/api", tags=["response-comments"])
app.include_router(personalities_router, prefix="/api/personalities", tags=["personalities"])
app.include_router(workspaces_router, prefix="/api", tags=["workspaces"])
app.include_router(enhanced_projects_router, prefix="/api/enhanced-projects", tags=["enhanced-projects"])

# Set up uploads directory (use /tmp on Vercel due to read-only filesystem)
if os.getenv("VERCEL") == "1":
    UPLOADS_DIR = "/tmp/uploads"
    logger.info(f"Running on Vercel, using {UPLOADS_DIR} for temporary uploads")
else:
    UPLOADS_DIR = "uploads"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOADS_DIR, "images"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Add a simple CORS test endpoint
@app.get("/cors-test")
async def cors_test():
    return {"message": "CORS is working!", "status": "success"}

# Root endpoint for Railway health checks
@app.get("/")
@app.get("/api")
async def root():
    """Root endpoint for Railway health checks"""
    return {
        "message": "PhatagiAI Backend is running!",
        "status": "healthy",
        "version": "1.0.0"
    }

# Health check endpoint
@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint with database connectivity test"""
    try:
        from app.services.database import check_database_health
        db_healthy = await check_database_health()
        
        if db_healthy:
            return {
                "status": "healthy",
                "database": "connected",
                "message": "All systems operational"
            }
        else:
            return {
                "status": "degraded",
                "database": "disconnected",
                "message": "Database connection issues detected"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "error",
            "message": f"Health check failed: {str(e)}"
        }


if __name__ == "__main__":
    import uvicorn
    # Railway requires binding to PORT environment variable
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 

import sys
import os

# Add the backend directory to Python path
# Now that we are in /backend, the path is just the current directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set environment variables for Vercel
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

handler = None

try:
    # Try to import the full FastAPI app from main.py
    from main import app as fastapi_app
    print("✅ Successfully imported main app")
    handler = fastapi_app
    
except Exception as e:
    print(f"❌ Failed to import main app: {e}")
    print("🔄 Falling back to simple app...")
    
    # Fall back to the simple app
    try:
        from api.simple import app as simple_app
        print("✅ Successfully imported simple app")
        handler = simple_app
    except Exception as e2:
        print(f"❌ Failed to import simple app: {e2}")
        
        # Create a minimal error handler
        try:
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse
            from fastapi.middleware.cors import CORSMiddleware
            
            error_app = FastAPI()
            
            # Add CORS to error handler too
            error_app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            @error_app.get("/")
            @error_app.get("/{path:path}")
            async def error_handler(path: str = ""):
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Backend failed to start: {str(e)} | {str(e2)}"}
                )
            
            handler = error_app
        except Exception as e3:
            print(f"❌ Failed to create error handler: {e3}")
            # Ultimate fallback
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse
            
            minimal_app = FastAPI()
            
            @minimal_app.get("/")
            @minimal_app.get("/{path:path}")
            async def minimal_handler(path: str = ""):
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Backend completely failed: {str(e)} | {str(e2)} | {str(e3)}"}
                )
            
            handler = minimal_app

# Set required Vercel exports
app = handler
application = handler

# Export for Vercel
__all__ = ['app', 'application', 'handler']

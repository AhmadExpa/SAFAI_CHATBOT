from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
import uuid
import os
import secrets
from sqlalchemy.dialects.postgresql import UUID
import smtplib
from email.mime.text import MIMEText
from authlib.integrations.starlette_client import OAuth
import logging
import hashlib

router = APIRouter()

# Rate limiting will be applied via middleware in main.py
# Individual routes can also use decorators if needed

# Import the enhanced database configuration
from app.services.database import engine, get_async_session
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(Text, nullable=False)  # hashed
    created_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    token = Column(String, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    expires = Column(DateTime, nullable=False)
    user = relationship("User")

class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"
    token = Column(String, primary_key=True, index=True)
    expires = Column(DateTime, nullable=False)

# Generate a secure SECRET_KEY if not provided
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Raise error if SECRET_KEY is not set in production
    if os.getenv("RAILWAY_ENVIRONMENT") == "true" or os.getenv("RAILWAY_PROJECT_ID"):
        raise ValueError("SECRET_KEY environment variable must be set in production!")
    
    # Generate a secure 32-character secret key for dev
    SECRET_KEY = secrets.token_urlsafe(32)
    print(f"🔑 Generated temporary SECRET_KEY for development: {SECRET_KEY}")
else:
    # Don't print the key in production
    if not (os.getenv("RAILWAY_ENVIRONMENT") == "true" or os.getenv("RAILWAY_PROJECT_ID")):
        print(f"🔑 Using provided SECRET_KEY: {SECRET_KEY[:5]}... (truncated)")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
# Set to 30 minutes to effectively make tokens expire in 30 minutes
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 minutes expiry time is fair enough and standard

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
PASSWORD_SCHEME_PREFIX = "sha256$"

# Log bcrypt version for debugging
try:
    import bcrypt
    print(f"🔍 bcrypt version: {bcrypt.__version__}")
except Exception as e:
    print(f"❌ Could not get bcrypt version: {e}")

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

async def get_db():
    async for session in get_async_session():
        yield session


def hash_password(password: str) -> str:
    """Hash passwords safely, including passwords longer than bcrypt's 72-byte limit."""
    normalized_password = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"{PASSWORD_SCHEME_PREFIX}{pwd_context.hash(normalized_password)}"


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verify a password and return an upgraded hash when legacy hashes are encountered."""
    normalized_password = hashlib.sha256(password.encode("utf-8")).hexdigest()

    if password_hash.startswith(PASSWORD_SCHEME_PREFIX):
        stored_hash = password_hash[len(PASSWORD_SCHEME_PREFIX):]
        return pwd_context.verify(normalized_password, stored_hash), None

    password_valid = pwd_context.verify(password, password_hash)
    if not password_valid:
        return False, None

    return True, hash_password(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    # Use 30 minutes as default expiration to make tokens effectively expire in 30 minutes
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    to_encode.update({"exp": expire})
    # Secure logging - do not print full token or secret
    # print(f"[DEBUG] Creating token with SECRET_KEY: {SECRET_KEY}, ALGORITHM: {ALGORITHM}")
    # print(f"[DEBUG] Token expiration: {expire} (30 minutes from now)")
    # print(f"[DEBUG] Token data: {to_encode}")
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    # print(f"[DEBUG] Created token: {token[:50]}...")
    return token

# SMTP configuration (set these for your email provider)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "your@email.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "yourpassword")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)

def send_email(to: str, subject: str, body: str):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to], msg.as_string())
    except Exception as e:
        print(f"[Email not sent] To: {to}, Subject: {subject}, Body: {body}, Error: {e}")

@router.post("/register")
async def register(user: UserRegister, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        logging.info(f"Registration attempt for email: {user.email}")
        
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == user.email))
        db_user = result.scalar_one_or_none()
        
        if db_user:
            logging.warning(f"User already exists: {user.email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = hash_password(user.password)
        
        # Create user with full_name stored in username field
        new_user = User(username=user.full_name, email=user.email, password=hashed_password)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logging.info(f"Successful registration for email: {user.email}")
        return {
            "user_id": str(new_user.user_id), 
            "email": new_user.email, 
            "full_name": new_user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        logging.error(f"Registration error: {error_msg}")
        logging.error(f"Traceback: {traceback_msg}")
        print(f"❌ Registration error: {error_msg}")
        print(f"❌ Traceback: {traceback_msg}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {error_msg}")

@router.post("/login")
async def login(user: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        # Check connection pool status before proceeding
        from app.services.database import get_connection_pool_status
        pool_status = await get_connection_pool_status()
        if pool_status:
            logging.info(f"Connection pool status: {pool_status}")
            if pool_status['checked_out'] > 8:  # Close to limit
                logging.warning(f"High connection usage: {pool_status['checked_out']} connections in use")
        
        logging.info(f"Login attempt for email: {user.email}")
        logging.info(f"Database session: {db}")
        logging.info(f"User model: {User}")
        
        logging.info("Executing database query...")
        result = await db.execute(select(User).where(User.email == user.email))
        logging.info("Database query executed successfully")
        
        db_user = result.scalar_one_or_none()
        logging.info(f"Database user found: {db_user is not None}")
        
        if not db_user:
            logging.warning(f"User not found for email: {user.email}")
            raise HTTPException(status_code=401, detail="User not registered")

        password_valid, updated_hash = verify_password(user.password, db_user.password)
        if password_valid and updated_hash:
            db_user.password = updated_hash
            await db.commit()
            logging.info(f"Upgraded password hash for email: {user.email}")
        
        if not password_valid:
            logging.warning(f"Invalid password for email: {user.email}")
            raise HTTPException(status_code=401, detail="Password is not correct.")
        
        # Use email as the subject in the JWT (tokens set to never expire - 100 years)
        access_token = create_access_token(data={"sub": db_user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        
        logging.info(f"Successful login for email: {user.email}")
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user": {
                "id": str(db_user.user_id),
                "email": db_user.email,
                "full_name": db_user.username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Login error: {str(e)}")
        logging.error(f"Full traceback: {error_details}")
        
        # Handle specific database connection errors
        if "getaddrinfo failed" in str(e) or "11002" in str(e):
            logging.error("❌ Network connectivity issue detected")
            logging.error("   - Cannot resolve database hostname")
            logging.error("   - Please check your internet connection")
            logging.error("   - Verify the database URL is correct")
            
            # Test database connection
            try:
                from app.services.database import test_database_connection
                await test_database_connection()
            except Exception as test_error:
                logging.error(f"Database connection test failed: {test_error}")
                
        elif "MaxClientsInSessionMode" in str(e) or "max clients reached" in str(e).lower():
            logging.warning("Connection pool exhausted, attempting to reset...")
            try:
                from app.services.database import reset_connection_pool
                await reset_connection_pool()
                logging.info("Connection pool reset successfully")
            except Exception as reset_error:
                logging.error(f"Failed to reset connection pool: {reset_error}")
        
        raise HTTPException(status_code=500, detail=f"Internal server error during login: {str(e)}")

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User with this email does not exist.")
    # Generate a secure token
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=1)
    # Store the token in the database
    db_token = PasswordResetToken(token=token, user_id=db_user.user_id, expires=expires)
    db.add(db_token)
    await db.commit()
    # Send the token to the user's email
    send_email(
        to=request.email,
        subject="Password Reset",
        body=f"Your password reset token is: {token}"
    )
    return {"message": f"Password reset instructions sent to {request.email}."}

def get_token_from_header(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    return auth_header.split(" ", 1)[1]

async def check_blacklist(request: Request, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS blacklisted_tokens (
                token VARCHAR PRIMARY KEY,
                expires TIMESTAMP NOT NULL
            )
            """
        )
    )
    token = get_token_from_header(request)
    result = await db.execute(select(BlacklistedToken).where(BlacklistedToken.token == token))
    blacklisted = result.scalar_one_or_none()
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked. Please log in again.")
    return token

@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS blacklisted_tokens (
                token VARCHAR PRIMARY KEY,
                expires TIMESTAMP NOT NULL
            )
            """
        )
    )
    token = get_token_from_header(request)
    try:
        # Decode token to get expiry
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if not exp:
            raise HTTPException(status_code=400, detail="Token missing expiry.")
        expires = datetime.utcfromtimestamp(exp)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token.")

    db_token = BlacklistedToken(token=token, expires=expires)
    db.add(db_token)
    await db.commit()
    return {"message": "Successfully logged out. Token has been revoked."}

# Example of a protected route using the blacklist check
def get_current_user(request: Request = Depends(check_blacklist)):
    token = get_token_from_header(request)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")

@router.get("/me")
async def read_users_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(check_blacklist)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload.")

        result = await db.execute(select(User).where(User.email == email))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found.")

        return {
            "id": str(db_user.user_id),
            "email": db_user.email,
            "full_name": db_user.username,
            "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
        }
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")

# NOTE: You must create the password_reset_tokens table in your database (via Alembic migration or manual SQL) for this to work in production.

# OAuth setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Could not get user info from Google")
            
        email = user_info['email']
        username = user_info.get('name', email.split('@')[0])

        # Check if user exists, else create
        result = await db.execute(select(User).where(User.email == email))
        db_user = result.scalar_one_or_none()
        if not db_user:
            db_user = User(username=username, email=email, password="")
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)

        # Issue JWT (tokens set to never expire - 100 years)
        access_token = create_access_token(data={"sub": db_user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        
        # Return a redirect to frontend with token
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return JSONResponse(
            status_code=302,
            headers={"Location": f"{frontend_url}/chat?token={access_token}"}
        )
    except Exception as e:
        logging.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail="Google authentication failed")

@router.get("/pool-status")
async def get_pool_status():
    """Get database connection pool status for debugging"""
    try:
        from app.services.database import get_connection_pool_status
        pool_status = await get_connection_pool_status()
        return JSONResponse(
            status_code=200,
            content={"pool_status": pool_status}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get pool status: {str(e)}"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )

@router.post("/reset-pool")
async def reset_pool():
    """Reset database connection pool"""
    try:
        from app.services.database import reset_connection_pool
        await reset_connection_pool()
        return JSONResponse(
            status_code=200,
            content={"message": "Connection pool reset successfully"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to reset pool: {str(e)}"}
        )

@router.get("/test-connection")
async def test_connection():
    """Test database connection"""
    try:
        from app.services.database import test_database_connection
        success = await test_database_connection()
        if success:
            return JSONResponse(
                status_code=200,
                content={"message": "Database connection successful"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "Database connection failed"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Connection test failed: {str(e)}"}
        )

@router.get("/health")
async def health_check():
    """Comprehensive health check for the application"""
    try:
        from app.services.database import get_connection_pool_status, test_database_connection
        
        # Test database connection
        db_healthy = await test_database_connection()
        
        # Get pool status
        pool_status = await get_connection_pool_status()
        
        health_status = {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected",
            "pool_status": pool_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        status_code = 200 if db_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Health check failed: {str(e)}"}
        )
@router.get("/dns-test")
async def test_dns_status():
    """Test DNS resolution for database hostname"""
    try:
        from app.services.database import test_dns_resolution
        dns_success = await test_dns_resolution()
        
        if dns_success:
            return {"message": "DNS resolution successful", "status": "success"}
        else:
            raise HTTPException(status_code=500, detail="DNS resolution failed")
    except Exception as e:
        logger.error(f"DNS test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

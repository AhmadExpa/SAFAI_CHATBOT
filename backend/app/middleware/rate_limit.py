"""
Rate limiting middleware for FastAPI
Protects against DDoS attacks by limiting request rates per IP address
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from starlette.responses import JSONResponse
import os

# Initialize rate limiter
# Using in-memory storage (for production, consider Redis)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour"],  # Default: 1000 requests per hour per IP
    storage_uri="memory://",  # In-memory storage
)

# Custom rate limit exceeded handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors
    Returns a JSON response with error details
    """
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"Too many requests. Limit: {exc.detail}. Please try again later.",
            "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else None
        }
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response

# Rate limit configurations for different endpoints
# These can be customized per route
RATE_LIMITS = {
    # Authentication endpoints - stricter limits
    "auth": {
        "login": "5/minute",  # 5 login attempts per minute
        "register": "3/hour",  # 3 registrations per hour
        "forgot_password": "3/hour",  # 3 password reset requests per hour
        "default": "10/minute"  # Default for other auth endpoints
    },
    # Chat endpoints - moderate limits
    "chat": {
        "default": "60/minute",  # 60 messages per minute
        "streaming": "30/minute"  # 30 streaming requests per minute
    },
    # API endpoints - moderate limits
    "api": {
        "conversations": "100/hour",  # 100 conversation requests per hour
        "projects": "200/hour",  # 200 project requests per hour
        "files": "50/hour",  # 50 file operations per hour
        "default": "500/hour"  # Default for other API endpoints
    },
    # General endpoints
    "default": "1000/hour"  # Default: 1000 requests per hour
}

def get_rate_limit_for_endpoint(endpoint_path: str) -> str:
    """
    Determine the appropriate rate limit for an endpoint based on its path
    """
    path_lower = endpoint_path.lower()
    
    # Check auth endpoints
    if "/auth/" in path_lower:
        if "login" in path_lower:
            return RATE_LIMITS["auth"]["login"]
        elif "register" in path_lower:
            return RATE_LIMITS["auth"]["register"]
        elif "forgot" in path_lower or "reset" in path_lower:
            return RATE_LIMITS["auth"]["forgot_password"]
        return RATE_LIMITS["auth"]["default"]
    
    # Check chat endpoints
    if "/chat" in path_lower or "/openai" in path_lower or "/xai" in path_lower or "/qwen" in path_lower or "/moonshot" in path_lower:
        if "stream" in path_lower:
            return RATE_LIMITS["chat"]["streaming"]
        return RATE_LIMITS["chat"]["default"]
    
    # Check API endpoints
    if "/api/" in path_lower:
        if "conversation" in path_lower:
            return RATE_LIMITS["api"]["conversations"]
        elif "project" in path_lower:
            return RATE_LIMITS["api"]["projects"]
        elif "file" in path_lower:
            return RATE_LIMITS["api"]["files"]
        return RATE_LIMITS["api"]["default"]
    
    # Default rate limit
    return RATE_LIMITS["default"]


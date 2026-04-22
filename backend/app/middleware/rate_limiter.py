"""
Rate limiting middleware using slowapi
Applies rate limits to all requests to prevent DDoS attacks
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from starlette.responses import JSONResponse
from app.middleware.rate_limit import get_rate_limit_for_endpoint

def create_rate_limiter():
    """Create and configure rate limiter"""
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000/hour"],  # Default: 1000 requests per hour per IP
        storage_uri="memory://",  # In-memory storage (use Redis for production)
    )
    return limiter

def create_rate_limit_handler():
    """Create custom rate limit exceeded handler"""
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """
        Custom handler for rate limit exceeded errors
        Returns a JSON response with error details
        """
        response = JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Too many requests. Please try again later.",
                "message": "You have exceeded the rate limit for this endpoint. Please wait before making more requests."
            },
            headers={
                "Retry-After": str(exc.retry_after) if hasattr(exc, 'retry_after') and exc.retry_after else "60",
                "X-RateLimit-Limit": str(exc.detail) if hasattr(exc, 'detail') else "unknown",
            }
        )
        return response
    return rate_limit_handler


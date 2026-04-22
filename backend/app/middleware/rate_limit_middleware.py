"""
Rate limiting middleware for FastAPI
Applies rate limits globally to prevent DDoS attacks
"""
from fastapi import Request
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import get_rate_limit_for_endpoint
import time
from collections import defaultdict
from typing import Dict, Tuple

# Simple in-memory rate limit storage
# In production, use Redis for distributed rate limiting
_rate_limit_storage: Dict[str, Dict[str, Tuple[int, float]]] = defaultdict(dict)

def check_rate_limit(request: Request, limiter: Limiter = None) -> bool:
    """
    Check if request is within rate limit
    Returns True if allowed, False if rate limit exceeded
    """
    client_ip = get_remote_address(request)
    endpoint_path = request.url.path
    rate_limit_str = get_rate_limit_for_endpoint(endpoint_path)
    
    # Parse rate limit (e.g., "5/minute" -> count=5, period="minute")
    import re
    match = re.match(r"(\d+)/(\w+)", rate_limit_str)
    if not match:
        return True  # If parsing fails, allow the request
    
    count = int(match.group(1))
    period = match.group(2)
    
    # Convert period to seconds
    period_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400
    }.get(period, 60)
    
    # Create a key for this IP and endpoint combination
    key = f"{client_ip}:{endpoint_path}"
    current_time = time.time()
    
    # Get existing requests for this key
    if key in _rate_limit_storage:
        requests = _rate_limit_storage[key]
        # Remove old entries outside the time window
        cutoff_time = current_time - period_seconds
        requests = {k: v for k, v in requests.items() if v[1] > cutoff_time}
        _rate_limit_storage[key] = requests
        
        # Check if limit exceeded
        if len(requests) >= count:
            return False
    
    # Add this request
    request_id = str(current_time)
    _rate_limit_storage[key][request_id] = (1, current_time)
    
    # Clean up old entries periodically (every 1000 requests)
    if len(_rate_limit_storage) > 1000:
        _rate_limit_storage.clear()
    
    return True

async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware function
    """
    # Skip rate limiting for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)
    
    # Check rate limit using our custom implementation
    # Note: We don't need the limiter from app state since we use our own logic
    if not check_rate_limit(request, None):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": "Too many requests. Please try again later.",
                "message": "You have exceeded the rate limit for this endpoint. Please wait before making more requests."
            },
            headers={
                "Retry-After": "60",
            }
        )
    
    # Continue with the request
    return await call_next(request)


"""
Helper function to apply rate limiting to routes
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def apply_rate_limit(limiter: Limiter, limit: str):
    """
    Create a decorator to apply rate limiting to a route
    Usage: @apply_rate_limit(limiter, "5/minute")
    """
    def decorator(func):
        # Apply the rate limit decorator
        return limiter.limit(limit)(func)
    return decorator


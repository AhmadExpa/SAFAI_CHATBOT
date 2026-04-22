import os
from typing import Any, Optional

from dotenv import load_dotenv

from app.config.logging import get_logger

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[assignment]
    create_client = None

load_dotenv()
logger = get_logger(__name__)

# Lazy initialization of Supabase client
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Optional[Client]:
    """Get Supabase client with lazy initialization"""
    global _supabase_client

    if _supabase_client is None:
        if create_client is None:
            logger.warning("Supabase SDK is not installed; skipping Supabase client initialization")
            return None

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if supabase_url and supabase_key:
            try:
                _supabase_client = create_client(supabase_url, supabase_key)
            except Exception as e:
                logger.warning(f"Could not initialize Supabase client: {e}")
                return None
        else:
            logger.warning("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set")
            return None

    return _supabase_client

# For backward compatibility, but don't create client at import time
supabase = None

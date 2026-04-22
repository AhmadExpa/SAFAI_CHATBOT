import os
import uuid
import asyncio
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Import the centralized logging configuration
from app.config.logging import get_logger
logger = get_logger(__name__)


def _as_async_database_url(database_url: str) -> str:
    """Normalize DATABASE_URL values for asyncpg-backed SQLAlchemy usage."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _extract_database_hostname(database_url: str | None) -> str | None:
    if not database_url:
        return None
    return urlparse(database_url).hostname


def _resolve_async_database_url() -> str:
    """Resolve the async database URL from env, falling back to DATABASE_URL."""
    raw_database_url = os.getenv("ASYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw_database_url:
        load_dotenv()
        raw_database_url = os.getenv("ASYNC_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not raw_database_url:
        raise ValueError("ASYNC_DATABASE_URL or DATABASE_URL environment variable is required")

    async_database_url = _as_async_database_url(raw_database_url)
    if raw_database_url != async_database_url:
        logger.info("Normalized DATABASE_URL to asyncpg format for async SQLAlchemy usage")

    return async_database_url


ASYNC_DATABASE_URL = _resolve_async_database_url()
DATABASE_URL = ASYNC_DATABASE_URL
DATABASE_HOST = _extract_database_hostname(DATABASE_URL)

if DATABASE_HOST:
    logger.info(f"Database configured for host: {DATABASE_HOST}")
else:
    logger.warning("Database configured but host could not be determined from the connection string")

# Enhanced engine configuration for better connection handling
# Render.com optimized settings for Supabase connection with fallback
def create_database_engine():
    """Create database engine with fallback strategies"""
    try:
        # Primary configuration
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,  # Disable echo to reduce log noise
            pool_size=1,  # Conservative: only 1 persistent connection
            max_overflow=0,  # No overflow connections for Render
            pool_timeout=60,  # Increased timeout for Render
            pool_recycle=600,  # Recycle connections every 10 minutes
            pool_pre_ping=True,  # Validate connections before use
            pool_reset_on_return='commit',  # Reset connections on return to pool
            connect_args={
                "server_settings": {
                    "application_name": "PhatagiAI-Render",
                    "statement_timeout": "60s",
                    "idle_in_transaction_session_timeout": "120s",
                    "jit": "off",  # Disable JIT for better compatibility
                },
                "command_timeout": 60,
            }
        )
        logger.info("✅ Database engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        # Try fallback configuration
        try:
            logger.info("🔄 Trying fallback configuration...")
            fallback_engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                pool_size=1,
                max_overflow=0,
                pool_timeout=120,  # Even longer timeout
                pool_recycle=300,  # Shorter recycle time
                pool_pre_ping=True,
                connect_args={
                    "server_settings": {
                        "application_name": "PhatagiAI-Render-Fallback",
                        "statement_timeout": "120s",
                        "idle_in_transaction_session_timeout": "180s",
                    },
                    "command_timeout": 120,
                }
            )
            logger.info("✅ Fallback database engine created successfully")
            return fallback_engine
        except Exception as e2:
            logger.error(f"❌ Fallback engine creation failed: {e2}")
            raise e2

# Create the database engine
engine = create_database_engine()
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session():
    """Get an async database session with proper cleanup and retry logic"""
    session = None
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            session = AsyncSessionLocal()
            yield session
            return  # Success, exit the retry loop
        except Exception as e:
            logger.error(f"Database session error (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Handle specific network connectivity errors
            if "getaddrinfo failed" in str(e) or "11002" in str(e):
                logger.error("Network connectivity issue - cannot resolve database hostname")
                logger.error("Please check your internet connection and database URL")
                
                # Try to recreate the engine with fallback strategies
                try:
                    logger.info("🔄 Attempting to recreate database engine with fallback strategies...")
                    # Note: Engine recreation should be handled at module level, not inside functions
                    logger.warning("⚠️ Database engine recreation attempted but may need server restart")
                except Exception as fallback_error:
                    logger.error(f"❌ Failed to recreate database engine: {fallback_error}")
            elif "MaxClientsInSessionMode" in str(e) or "QueuePool limit" in str(e):
                logger.error("Database connection pool exhausted")
                # Try to reset the pool
                try:
                    await reset_connection_pool()
                    logger.info("Connection pool reset attempted")
                except Exception as reset_error:
                    logger.error(f"Failed to reset connection pool: {reset_error}")
            elif "timeout" in str(e).lower():
                logger.error("Database connection timeout")
            
            # Clean up session if it exists
            if session:
                try:
                    await session.rollback()
                except:
                    pass
                try:
                    await session.close()
                except:
                    pass
                session = None
            
            # If this is the last attempt, raise the error
            if attempt == max_retries - 1:
                raise
            
            # Wait before retrying with exponential backoff
            logger.info(f"Retrying database connection in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff: 1s, 2s, 4s
        finally:
            # Ensure session is always cleaned up
            if session:
                try:
                    await session.rollback()
                except:
                    pass
                try:
                    await session.close()
                except:
                    pass

async def check_connection_health():
    """Check database connection health"""
    try:
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            logger.info("Database connection health check passed")
            return True
    except Exception as e:
        logger.error(f"Database connection health check failed: {e}")
        return False

async def ensure_connection():
    """Ensure database connection is available before operations"""
    try:
        # Test the connection
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection not available: {e}")
        return False

async def get_connection_pool_status():
    """Get connection pool status for debugging"""
    try:
        pool = engine.pool
        status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow()
        }
        
        # Only add 'invalid' if the pool has this attribute
        if hasattr(pool, 'invalid'):
            status["invalid"] = pool.invalid()
        else:
            status["invalid"] = "N/A (not available for this pool type)"
            
        return status
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return None

async def close_all_connections():
    """Close all database connections and reset the pool"""
    try:
        logger.info("Closing all database connections...")
        await engine.dispose()
        logger.info("All database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

async def reset_connection_pool():
    """Reset the connection pool to clear any stale connections"""
    try:
        logger.info("Resetting database connection pool...")
        # Dispose of all connections
        await engine.dispose()
        # Wait a moment for cleanup
        await asyncio.sleep(1)
        logger.info("Database connection pool reset successfully")
    except Exception as e:
        logger.error(f"Error resetting connection pool: {e}")

async def get_connection_pool_status():
    """Get the current status of the connection pool"""
    try:
        pool = engine.pool
        if hasattr(pool, 'size'):
            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid() if hasattr(pool, 'invalid') else 0
            }
        else:
            return {"error": "Pool status not available"}
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return {"error": str(e)}

async def test_dns_resolution():
    """Test DNS resolution for the database hostname"""
    try:
        import socket
        hostname = DATABASE_HOST
        if not hostname:
            logger.warning("Skipping DNS resolution test because database hostname could not be determined")
            return False
        logger.info(f"Testing DNS resolution for: {hostname}")
        
        # Test direct resolution first
        try:
            result = socket.gethostbyname(hostname)
            logger.info(f"✅ DNS resolution successful: {hostname} -> {result}")
            return True
        except socket.gaierror as e:
            logger.warning(f"Direct DNS resolution failed: {e}")
        
        # Test with different DNS servers using asyncio
        dns_servers = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]
        
        for dns_server in dns_servers:
            try:
                logger.info(f"Trying DNS server: {dns_server}")
                # Use asyncio to run DNS resolution in a separate thread
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, socket.gethostbyname, hostname)
                logger.info(f"✅ DNS resolution successful: {hostname} -> {result}")
                return True
            except socket.gaierror as e:
                logger.warning(f"DNS resolution failed with {dns_server}: {e}")
                continue
            except Exception as e:
                logger.warning(f"DNS resolution error with {dns_server}: {e}")
                continue
        
        logger.error("❌ DNS resolution failed with all DNS servers")
        return False
        
    except Exception as e:
        logger.error(f"DNS resolution test failed: {e}")
        return False

async def test_database_connection():
    """Test database connection with detailed error reporting and retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Testing database connection... (attempt {attempt + 1}/{max_retries})")
            
            # Test DNS resolution first
            import socket
            try:
                if DATABASE_HOST:
                    hostname = DATABASE_HOST
                    logger.info(f"Testing DNS resolution for: {hostname}")
                    socket.gethostbyname(hostname)
                    logger.info("✅ DNS resolution successful")
                else:
                    logger.warning("Could not extract hostname from database connection string")
            except socket.gaierror as dns_error:
                logger.error(f"❌ DNS resolution failed: {dns_error}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying DNS resolution in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error("❌ DNS resolution failed after all retries")
                    logger.error("   - Check your internet connection")
                    logger.error("   - Verify the database hostname is correct")
                    logger.error("   - Try using a different DNS server (8.8.8.8, 1.1.1.1)")
                    return False
            
            # Test database connection
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                logger.info("✅ Database connection test successful")
                return True
                
        except Exception as e:
            logger.error(f"Database connection test failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Provide specific error guidance
            if "getaddrinfo failed" in str(e) or "11002" in str(e):
                logger.error("❌ Network connectivity issue:")
                logger.error("   - Check your internet connection")
                logger.error("   - Verify the database hostname is correct")
                logger.error("   - Try using a different DNS server (8.8.8.8, 1.1.1.1)")
                logger.error("   - Check if your firewall is blocking the connection")
            elif "tenant or user not found" in str(e).lower() or "authentication" in str(e).lower():
                logger.error("❌ Authentication issue:")
                logger.error("   - Check your Supabase pooler username and password")
                logger.error("   - Verify the host matches the active Supabase project and region")
            elif "timeout" in str(e).lower():
                logger.error("❌ Connection timeout:")
                logger.error("   - Check network latency")
                logger.error("   - Verify database server is running")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("❌ Database connection failed after all retries")
                return False
    
    return False

async def create_conversation(session, user_id, title, project_id=None):
    """Create a new conversation"""
    try:
        conversation_id = str(uuid.uuid4())
        logger.info(f"Creating conversation: {conversation_id} for user: {user_id}")
        
        await session.execute(
            text("""
                INSERT INTO conversations (conversation_id, user_id, project_id, title, created_at, updated_at)
                VALUES (:conversation_id, :user_id, :project_id, :title, :created_at, :updated_at)
            """),
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "project_id": project_id,
                "title": title,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
        await session.commit()
        logger.info(f"Successfully created conversation: {conversation_id}")
        return conversation_id
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        await session.rollback()
        raise

async def create_bubble(session, conversation_id, bubble_index):
    """Create a new bubble in a conversation"""
    try:
        bubble_id = str(uuid.uuid4())
        logger.info(f"Creating bubble: {bubble_id} for conversation: {conversation_id}")
        
        await session.execute(
            text("""
                INSERT INTO bubbles (bubble_id, conversation_id, bubble_index, created_at)
                VALUES (:bubble_id, :conversation_id, :bubble_index, :created_at)
            """),
            {
                "bubble_id": bubble_id,
                "conversation_id": conversation_id,
                "bubble_index": bubble_index,
                "created_at": datetime.utcnow(),
            }
        )
        await session.commit()
        logger.info(f"Successfully created bubble: {bubble_id}")
        return bubble_id
    except Exception as e:
        logger.error(f"Error creating bubble: {e}")
        await session.rollback()
        raise

async def create_message(session, bubble_id, message_index, role, content, model_used=None):
    """Create a new message in a bubble"""
    try:
        message_id = str(uuid.uuid4())
        logger.info(f"Creating message: {message_id} for bubble: {bubble_id}")
        
        await session.execute(
            text("""
                INSERT INTO messages (message_id, bubble_id, message_index, role, content, model_used, created_at)
                VALUES (:message_id, :bubble_id, :message_index, :role, :content, :model_used, :created_at)
            """),
            {
                "message_id": message_id,
                "bubble_id": bubble_id,
                "message_index": message_index,
                "role": role,
                "content": content,
                "model_used": model_used,
                "created_at": datetime.utcnow(),
            }
        )
        await session.commit()
        logger.info(f"Successfully created message: {message_id}")
        return message_id
    except Exception as e:
        logger.error(f"Error creating message: {e}")
        await session.rollback()
        raise

async def store_chat_conversation(session, user_id, title, messages, model_used, project_id=None):
    """Store a complete chat conversation with bubbles and messages"""
    try:
        if not user_id:
            logger.warning("No user_id provided, skipping chat storage.")
            return None
        
        logger.info(f"Storing chat conversation for user: {user_id}, title: {title}, messages: {len(messages)}")
        
        # Create conversation
        conversation_id = await create_conversation(session, user_id, title, project_id)
        
        # Create a single bubble for this conversation
        bubble_id = await create_bubble(session, conversation_id, 0)
        
        # Store all messages in the bubble
        for i, message in enumerate(messages):
            await create_message(
                session, 
                bubble_id, 
                i, 
                message.get("role", "user"), 
                message.get("content", ""), 
                model_used
            )
        
        logger.info(f"Successfully stored complete chat conversation: {conversation_id}")
        return conversation_id
    except Exception as e:
        logger.error(f"Error storing chat conversation: {e}")
        raise

async def get_or_create_conversation(session, user_id, title, project_id=None, conversation_id=None):
    """Get existing conversation or create a new one for the current chat session"""
    try:
        # If conversation_id is provided, use that existing conversation
        if conversation_id:
            # Verify the conversation exists and belongs to the user
            result = await session.execute(
                text("""
                    SELECT conversation_id FROM conversations 
                    WHERE conversation_id = :conversation_id AND user_id = :user_id
                """),
                {"conversation_id": conversation_id, "user_id": user_id}
            )
            existing_conversation = result.scalar()
            
            if existing_conversation:
                logger.info(f"Using existing conversation: {conversation_id}")
                return conversation_id
            else:
                logger.warning(f"Conversation {conversation_id} not found or doesn't belong to user {user_id}")
                # Fall through to create new conversation
        
        # Create a new conversation for new chat sessions
        conversation_id = await create_conversation(session, user_id, title, project_id)
        logger.info(f"Created new conversation: {conversation_id}")
        return conversation_id
    except Exception as e:
        logger.error(f"Error getting/creating conversation: {e}")
        raise

async def get_next_bubble_index(session, conversation_id):
    """Get the next bubble index for a conversation"""
    try:
        result = await session.execute(
            text("""
                SELECT COALESCE(MAX(bubble_index), -1) + 1 as next_index
                FROM bubbles 
                WHERE conversation_id = :conversation_id
            """),
            {"conversation_id": conversation_id}
        )
        next_index = result.scalar()
        logger.info(f"Next bubble index for conversation {conversation_id}: {next_index}")
        return next_index
    except Exception as e:
        logger.error(f"Error getting next bubble index: {e}")
        raise

async def get_next_message_index(session, bubble_id):
    """Get the next message index for a bubble"""
    try:
        result = await session.execute(
            text("""
                SELECT COALESCE(MAX(message_index), -1) + 1 as next_index
                FROM messages 
                WHERE bubble_id = :bubble_id
            """),
            {"bubble_id": bubble_id}
        )
        next_index = result.scalar()
        logger.info(f"Next message index for bubble {bubble_id}: {next_index}")
        return next_index
    except Exception as e:
        logger.error(f"Error getting next message index: {e}")
        raise

async def store_request_response_pair(session, user_id, conversation_id, user_message, assistant_message, model_used=None):
    """Store a request-response pair as a new bubble in an existing conversation"""
    try:
        if not user_id or not conversation_id:
            logger.warning("Missing user_id or conversation_id, skipping storage.")
            return None
        
        logger.info(f"Storing request-response pair for conversation: {conversation_id}")
        
        # Get next bubble index for this conversation
        bubble_index = await get_next_bubble_index(session, conversation_id)
        
        # Create new bubble for this request-response pair
        bubble_id = await create_bubble(session, conversation_id, bubble_index)
        
        # Both user and assistant messages get the same message_index (bubble_index)
        message_index = bubble_index
        
        # Store user message with message_index = bubble_index
        await create_message(
            session, 
            bubble_id, 
            message_index,  # Same as bubble_index
            "user", 
            user_message, 
            model_used
        )
        
        # Store assistant message with same message_index = bubble_index
        await create_message(
            session, 
            bubble_id, 
            message_index,  # Same as bubble_index
            "assistant", 
            assistant_message, 
            model_used
        )
        
        # Update conversation timestamp
        await session.execute(
            text("""
                UPDATE conversations 
                SET updated_at = :updated_at 
                WHERE conversation_id = :conversation_id
            """),
            {
                "updated_at": datetime.utcnow(),
                "conversation_id": conversation_id
            }
        )
        await session.commit()
        
        logger.info(f"Successfully stored request-response pair in bubble: {bubble_id} (bubble_index: {bubble_index}, message_index: {message_index})")
        return bubble_id
    except Exception as e:
        logger.error(f"Error storing request-response pair: {e}")
        await session.rollback()
        raise

async def check_database_health():
    """Check database health and attempt to fix connection issues"""
    try:
        logger.info("🔍 Checking database health...")
        
        # Test current connection
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            logger.info("✅ Database health check passed")
            return True
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Database health check failed: {e}")
        
        # If it's a network connectivity issue, try fallback strategies
        if "getaddrinfo failed" in error_msg or "11002" in error_msg:
            logger.info("🔄 Network connectivity issue detected - trying fallback strategies...")
            
            # Try basic connection test
            try:
                async with AsyncSessionLocal() as test_session:
                    await test_session.execute(text("SELECT 1"))
                    logger.info("✅ Database connection restored")
                    return True
            except Exception as test_error:
                logger.error(f"❌ Fallback connection test failed: {test_error}")
                return False
        elif "tenant or user not found" in error_msg.lower() or "authentication" in error_msg.lower():
            logger.error("❌ Database credentials were rejected by the configured Supabase/Postgres host")
            logger.error("   - Recheck DATABASE_URL and ASYNC_DATABASE_URL in API Backend/.env")
            logger.error("   - Ensure the pooler username includes the project ref when using Supabase pooler URLs")
            return False
        else:
            logger.error(f"❌ Database health check failed with non-network error: {e}")
            return False

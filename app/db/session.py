from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from urllib.parse import urlsplit, urlunsplit
from app.core.config import settings


def _mask_db_url(url: str | None) -> str | None:
    if not url:
        return url
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            # Rebuild netloc without password
            if parts.username:
                netloc = f"{parts.username}:***@{parts.hostname or ''}"
            else:
                netloc = f"***@{parts.hostname or ''}"
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url
    except Exception:
        return "***"


# Create engine with error handling
try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,           # Detect stale connections
        pool_recycle=900,             # Recycle connections every 15 minutes
        pool_timeout=30,              # Wait up to 30s for a connection
        echo=False,                   # Set to True for SQL debugging
        pool_size=5,                  # Tune according to Railway plan
        max_overflow=5                # Allow short bursts
    )
    AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"Database connection error: {e}")
    print(f"DATABASE_URL: {_mask_db_url(settings.DATABASE_URL)}")
    raise

# Alias para compatibilidade
async_session = AsyncSessionLocal

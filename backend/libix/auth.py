"""JWT authentication utilities."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_config
from .models import User, UserRole

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    config = get_config()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=config.auth.jwt_expiry_hours
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, config.server.get_secret_key(), algorithm=ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decode a JWT access token.

    Returns the payload if valid, None otherwise.
    """
    config = get_config()
    try:
        payload = jwt.decode(token, config.server.get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    """Authenticate a user by username and password.

    Returns the user if authentication succeeds, None otherwise.
    """
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Get a user by their ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Get a user by their username."""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> User:
    """Create a new user."""
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def ensure_initial_admin(session: AsyncSession) -> None:
    """Create the initial admin user if no users exist."""
    config = get_config()

    # Check if any users exist
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    # Create initial admin
    admin_config = config.auth.initial_admin
    await create_user(
        session,
        username=admin_config.username,
        password=admin_config.get_password(),
        role=UserRole.ADMIN,
    )
    await session.commit()

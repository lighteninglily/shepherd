from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from ..core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from ..db.base import get_db
from ..models.user import (
    Token,
    User,
    UserCreate,
)


class AuthService:
    """Service for handling authentication and user management."""

    def __init__(self, db: Session):
        self.db = db

    async def register_user(self, user_create: UserCreate) -> User:
        """Register a new user.

        Args:
            user_create: User creation data

        Returns:
            User: The created user

        Raises:
            HTTPException: If the email is already registered
        """
        from ..models.sql_models import User as SQLUser
        # Check if user with email already exists
        existing_user = self.db.query(SQLUser).filter(SQLUser.email == user_create.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        # Hash the password
        hashed_password = get_password_hash(user_create.password)
        # Create user in database
        db_user = SQLUser(
            email=user_create.email,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,
            is_superuser=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        # Convert to API User model (exclude hashed_password)
        return User(
            id=db_user.id,
            email=db_user.email,
            is_active=db_user.is_active,
            is_verified=db_user.is_verified,
            is_superuser=db_user.is_superuser,
            last_login=db_user.last_login,
        )

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user.

        Args:
            email: User's email
            password: User's password

        Returns:
            Optional[User]: The authenticated user if successful, None otherwise
        """
        from ..models.sql_models import User as SQLUser
        user = self.db.query(SQLUser).filter(SQLUser.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return User(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            last_login=user.last_login,
        )

    async def login(self, email: str, password: str) -> Token:
        """Log in a user and return access and refresh tokens.

        Args:
            email: User's email
            password: User's password

        Returns:
            Token: Access and refresh tokens

        Raises:
            HTTPException: If authentication fails
        """
        user = await self.authenticate_user(email, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Update last login time in DB
        from ..models.sql_models import User as SQLUser
        db_user = self.db.query(SQLUser).filter(SQLUser.email == user.email).first()
        if db_user:
            db_user.last_login = datetime.now(timezone.utc)
            self.db.commit()
        # Create tokens
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = create_refresh_token(
            data={"sub": user.email}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        """Refresh access and refresh tokens.

        Args:
            refresh_token: The refresh token

        Returns:
            Token: New access and refresh tokens

        Raises:
            HTTPException: If the refresh token is invalid
        """
        try:
            payload = verify_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
                )
            email: str = payload.get("sub")
            if email is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
                )
            from ..models.sql_models import User as SQLUser
            user = self.db.query(SQLUser).filter(SQLUser.email == email).first()
            if user is None or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            # Create new tokens
            access_token = create_access_token(
                data={"sub": email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            new_refresh_token = create_refresh_token(
                data={"sub": email}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            )
            return Token(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

    # TODO: Add methods for password reset, email verification, etc.


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency for getting the auth service."""
    return AuthService(db)

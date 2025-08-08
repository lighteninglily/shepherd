from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ....models.user import Token, User, UserCreate
from ....services.auth import AuthService, get_auth_service
from ....core.security import get_current_active_user

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """
    Register a new user.

    Args:
        user_in: User registration data
        auth_service: Authentication service

    Returns:
        User: The created user
    """
    # No need to check for existing user separately, as register_user already does this check
    return await auth_service.register_user(user_in)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """
    Log in a user and return access and refresh tokens.

    Args:
        form_data: Login form data (username and password)
        auth_service: Authentication service

    Returns:
        Token: Access and refresh tokens
    """
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Use login method to create tokens
    return await auth_service.login(user.email, form_data.password)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """
    Refresh access and refresh tokens.

    Args:
        refresh_token: The refresh token
        auth_service: Authentication service

    Returns:
        Token: New access and refresh tokens
    """
    try:
        return await auth_service.refresh_tokens(refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=User)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get the current user.

    Args:
        current_user: The current authenticated user

    Returns:
        User: The current user
    """
    return current_user


# TODO: Add password reset endpoints
# @router.post("/password-reset")
# async def request_password_reset():
#     pass
#
# @router.post("/password-reset/confirm")
# async def reset_password():
#     pass

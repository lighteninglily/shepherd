from fastapi import APIRouter

from .endpoints import auth

api_router = APIRouter()

# Include all API routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# The following routers will be implemented later
# from .endpoints import conversations, prayers, users
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
# api_router.include_router(prayers.router, prefix="/prayers", tags=["Prayers"])

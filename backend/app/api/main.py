from fastapi import APIRouter

from app.api.routes import (
    accounts,
    admin,
    bots,
    login,
    notifications,
    private,
    subscriptions,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(accounts.router)
api_router.include_router(bots.router)
api_router.include_router(notifications.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)

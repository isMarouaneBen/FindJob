from fastapi import APIRouter

from app.api.v1 import admin, auth, cv, health, offers, profiles, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(offers.router)
api_router.include_router(profiles.router)
api_router.include_router(cv.router)
api_router.include_router(recommendations.router)
api_router.include_router(admin.router)

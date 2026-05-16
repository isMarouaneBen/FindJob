from fastapi import APIRouter

from app.api.v1 import cv, health, offers, profiles, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(offers.router)
api_router.include_router(profiles.router)
api_router.include_router(cv.router)
api_router.include_router(recommendations.router)

"""API v1 router: one sub-router per product module."""

from fastapi import APIRouter

from app.api.routers import companion, guard, insights, routines, secure_session, system

api_router = APIRouter(prefix="/api/v1")
for module in (system, guard, companion, insights, routines, secure_session):
    api_router.include_router(module.router)

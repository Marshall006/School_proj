"""Agregation des routeurs de la version 1 de l'API."""

from fastapi import APIRouter

from app.api.v1.routers import assessments, auth, catalog, children, devices, unlock

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(children.router)
api_router.include_router(devices.router)
api_router.include_router(unlock.router)
api_router.include_router(assessments.router)
api_router.include_router(catalog.router)

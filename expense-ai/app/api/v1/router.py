"""Versioned API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import approvals, chat, conversations


def build_v1_router() -> APIRouter:
    router = APIRouter()
    router.include_router(chat.router)
    router.include_router(conversations.router)
    router.include_router(approvals.router)
    return router

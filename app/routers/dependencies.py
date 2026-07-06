from typing import Optional
from fastapi import Request
from app.utils.cache import RedisCache
from app.services.dataset_service import DatasetService

def get_dataset_service(request: Request) -> DatasetService:
    """
    FastAPI dependency that provides a shared DatasetService instance.
    """
    return request.app.state.dataset_service

def get_cache(request: Request) -> Optional[RedisCache]:
    """
    FastAPI dependency that provides a shared RedisCache instance.
    """
    if hasattr(request.app.state, "cache"):
        return request.app.state.cache
    return None

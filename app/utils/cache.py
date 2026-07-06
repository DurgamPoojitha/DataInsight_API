"""
DataInsight API — Redis Cache Helper
====================================
Provides a reusable Redis client wrapper for caching Pydantic models.
"""

import json
from typing import TypeVar, Type, Optional

import redis
from pydantic import BaseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

class RedisCache:
    """
    Wrapper around a Redis connection for storing and retrieving Pydantic models.
    """
    def __init__(self, redis_url: str):
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)
            # Ping to verify connection
            self.client.ping()
            logger.info("Successfully connected to Redis cache", url=redis_url)
        except redis.RedisError as e:
            logger.warning(f"Failed to connect to Redis cache: {e}. Caching will be disabled.", url=redis_url)
            self.client = None

    def get(self, key: str, model_cls: Type[T]) -> Optional[T]:
        """
        Retrieve a value from the cache and deserialize it into a Pydantic model.
        """
        if not self.client:
            return None
            
        try:
            cached_data = self.client.get(key)
            if cached_data:
                return model_cls.model_validate_json(cached_data)
        except redis.RedisError as e:
            logger.warning(f"Redis GET failed for key {key}: {e}")
        except Exception as e:
            logger.warning(f"Failed to deserialize cache data for key {key}: {e}")
            
        return None

    def set(self, key: str, data: BaseModel, expire_seconds: int = 3600) -> bool:
        """
        Serialize a Pydantic model and store it in the cache.
        """
        if not self.client:
            return False
            
        try:
            # model_dump_json returns a string
            json_data = data.model_dump_json()
            return bool(self.client.setex(key, expire_seconds, json_data))
        except redis.RedisError as e:
            logger.warning(f"Redis SET failed for key {key}: {e}")
        except Exception as e:
            logger.warning(f"Failed to serialize cache data for key {key}: {e}")
            
        return False

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.
        """
        if not self.client:
            return False
            
        try:
            return bool(self.client.delete(key))
        except redis.RedisError as e:
            logger.warning(f"Redis DELETE failed for key {key}: {e}")
            return False

    def close(self):
        """
        Close the Redis connection.
        """
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

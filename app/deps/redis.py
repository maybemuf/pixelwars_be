from redis.asyncio import Redis

from app.core import settings

redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
import redis.asyncio as aioredis
import json
from typing import Optional, List, Dict
from app.models.log_models import NormalizedLogEntry

class LogStorageManager:
    def __init__(self, redis_url: str, buffer_size: int = 1000):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.buffer_size = buffer_size

    async def get_current_max_index(self) -> int:
        max_index = await self.redis.get("log_buffer:max_index")
        return int(max_index) if max_index else 0

    async def store_log(self, log: Dict) -> int:
        # Assign next log_index
        log_index = await self.redis.incr("log_buffer:max_index")
        # Remove log_index from storage
        log_to_store = log.copy()
        log_to_store.pop("log_index", None)
        await self.redis.set(f"log:{log_index}", json.dumps(log_to_store))
        # Buffer wraparound: delete oldest if over capacity
        if log_index > self.buffer_size:
            oldest_index = log_index - self.buffer_size
            await self.redis.delete(f"log:{oldest_index}")
            await self.redis.zrem("anomalies:sorted_set", oldest_index)
        return log_index

    async def get_log(self, log_index: int) -> Optional[Dict]:
        log_json = await self.redis.get(f"log:{log_index}")
        if not log_json:
            return None
        log = json.loads(log_json)
        log["log_index"] = log_index
        return log

    async def get_logs_range(self, start_index: int, end_index: int) -> List[Dict]:
        pipe = self.redis.pipeline()
        for idx in range(start_index, end_index + 1):
            pipe.get(f"log:{idx}")
        logs_json = await pipe.execute()
        logs = []
        for idx, log_json in enumerate(logs_json, start=start_index):
            if log_json:
                log = json.loads(log_json)
                log["log_index"] = idx
                logs.append(log)
        return logs

    async def flag_anomaly(self, log_index: int):
        # Mark is_anomaly in log and update indices
        log = await self.get_log(log_index)
        if not log:
            return False
        log["is_anomaly"] = True
        await self.redis.set(f"log:{log_index}", json.dumps({k: v for k, v in log.items() if k != "log_index"}))
        await self.redis.zadd("anomalies:sorted_set", {log_index: log_index})
        await self.redis.lpush("recent_anomalies:list", log_index)
        await self.redis.ltrim("recent_anomalies:list", 0, 99)
        return True

    async def get_anomaly_indices(self, start_index: int, end_index: int) -> List[int]:
        return [int(idx) for idx in await self.redis.zrangebyscore("anomalies:sorted_set", start_index, end_index)]

    async def get_recent_anomalies(self, count: int = 10) -> List[int]:
        return [int(idx) for idx in await self.redis.lrange("recent_anomalies:list", 0, count - 1)] 
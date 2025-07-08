import json
from typing import List, Any, Callable, Optional
from threading import Lock
from datetime import datetime, timedelta
import asyncio

"""
Buffer utilities for serialization, batching, and context window logic.
Logs now include a log_index field for index-based retrieval.
"""

class LogBuffer:
    """
    Thread-safe in-memory log buffer with batch management and stats.
    Drops oldest logs if buffer is full.
    """
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer: List[Any] = []
        self.lock = Lock()
        self.dropped_count = 0

    def add_log(self, log: Any):
        """
        Add a log entry to the buffer. Drop oldest if full.
        """
        with self.lock:
            if len(self.buffer) >= self.max_size:
                self.buffer.pop(0)
                self.dropped_count += 1
            self.buffer.append(log)

    def add_logs(self, logs: List[Any]):
        """
        Add multiple log entries to the buffer.
        """
        with self.lock:
            for log in logs:
                self.add_log(log)

    def get_logs(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get up to 'limit' logs from the buffer (newest last).
        """
        with self.lock:
            if limit:
                return self.buffer[-limit:]
            return list(self.buffer)

    def get_and_clear_batch(self, batch_size: int) -> List[Any]:
        """
        Get and remove a batch of logs from the buffer.
        """
        with self.lock:
            batch = self.buffer[:batch_size]
            self.buffer = self.buffer[batch_size:]
            return batch

    def clear(self):
        """
        Clear the buffer.
        """
        with self.lock:
            self.buffer.clear()
            self.dropped_count = 0

    def stats(self) -> dict:
        """
        Get buffer stats: size, utilization, oldest/newest timestamps, dropped count.
        """
        with self.lock:
            oldest = self.buffer[0].timestamp if self.buffer else None
            newest = self.buffer[-1].timestamp if self.buffer else None
            return {
                "size": len(self.buffer),
                "max_size": self.max_size,
                "utilization": len(self.buffer) / self.max_size,
                "oldest_timestamp": oldest,
                "newest_timestamp": newest,
                "dropped_count": self.dropped_count
            }

# --- Serialization Utilities ---
def serialize_log(log: Any) -> str:
    """Serialize a log entry to JSON string."""
    try:
        return json.dumps(log)
    except Exception:
        # Fallback: try model_dump if it's a Pydantic model
        if hasattr(log, 'model_dump'):
            return json.dumps(log.model_dump())
        raise

def deserialize_log(log_str: str) -> Any:
    """Deserialize a JSON string to a log entry (dict or model)."""
    return json.loads(log_str)

# --- Batching Utilities ---
def batch_iterable(iterable: List[Any], batch_size: int) -> List[List[Any]]:
    """Yield successive batches from a list."""
    for i in range(0, len(iterable), batch_size):
        yield iterable[i:i + batch_size]

# --- Time Window Logic ---
def filter_logs_by_time(logs: List[Any], start: datetime, end: datetime, timestamp_getter: Optional[Callable] = None) -> List[Any]:
    """Return logs whose timestamps are within [start, end]."""
    if not timestamp_getter:
        timestamp_getter = lambda log: log['timestamp'] if isinstance(log, dict) else getattr(log, 'timestamp', None)
    return [log for log in logs if start <= timestamp_getter(log) <= end]

def get_context_window(logs: List[Any], center_time: datetime, window: timedelta, timestamp_getter: Optional[Callable] = None) -> List[Any]:
    """Return logs within +/- window around center_time."""
    start = center_time - window
    end = center_time + window
    return filter_logs_by_time(logs, start, end, timestamp_getter)

# --- Async Utilities ---
async def run_with_retries(coro, retries=3, backoff=0.5, max_backoff=5.0, logger=None):
    """Run an async coroutine with retries and exponential backoff."""
    attempt = 0
    while True:
        try:
            return await coro()
        except Exception as e:
            attempt += 1
            if logger:
                logger.warning(f"Retry {attempt} failed: {e}")
            if attempt >= retries:
                raise
            await asyncio.sleep(min(backoff * (2 ** (attempt - 1)), max_backoff)) 
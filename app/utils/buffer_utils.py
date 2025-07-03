from typing import List, Optional, Any
from threading import Lock
from datetime import datetime

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
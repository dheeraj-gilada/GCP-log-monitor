import logging
from agents import function_tool
from app.services.log_storage_manager import LogStorageManager

# These tools now require a buffer argument and log debug info

def make_get_logs_by_index(log_storage: LogStorageManager):
    @function_tool
    async def get_logs_by_index(start_index: int, end_index: int) -> list:
        """Fetch logs from Redis by log_index range using LogStorageManager."""
        logs = await log_storage.get_logs_range(start_index, end_index)
        logging.info(f"[AGENT TOOL] get_logs_by_index({start_index}, {end_index}) returned {len(logs)} logs.")
        return logs
    return get_logs_by_index

def make_get_anomalies_by_index(log_storage: LogStorageManager):
    @function_tool
    async def get_anomalies_by_index(start_index: int, end_index: int) -> list:
        """Fetch anomalies from Redis by log_index range using LogStorageManager."""
        anomaly_indices = await log_storage.get_anomaly_indices(start_index, end_index)
        logs = await log_storage.get_logs_range(start_index, end_index)
        anomalies = [log for log in logs if log.get("log_index") in anomaly_indices and log.get("is_anomaly")]  # Defensive
        logging.info(f"[AGENT TOOL] get_anomalies_by_index({start_index}, {end_index}) returned {len(anomalies)} anomalies.")
        return anomalies
    return get_anomalies_by_index

class AnomalyGroupingTools:
    @staticmethod
    async def get_anomaly_logs(log_storage: LogStorageManager, start_index: int, end_index: int, limit: int = 100):
        """
        Fetch anomaly logs in a log_index range using ZRANGEBYSCORE and pipelined log fetch.
        Returns list of NormalizedLog objects where is_anomaly=True.
        """
        anomaly_indices = await log_storage.get_anomaly_indices(start_index, end_index)
        if limit:
            anomaly_indices = anomaly_indices[:limit]
        logs = await log_storage.get_logs_range(start_index, end_index)
        # Defensive: filter only those with is_anomaly and in anomaly_indices
        anomaly_logs = [log for log in logs if log.get("log_index") in anomaly_indices and log.get("is_anomaly")]
        return anomaly_logs

    @staticmethod
    async def get_contextual_logs(log_storage: LogStorageManager, center_index: int, window_size: int = 5):
        """
        Fetch logs around a specific log_index (±window_size).
        Returns all logs (anomaly + normal) in the range.
        """
        start = max(0, center_index - window_size)
        end = center_index + window_size
        logs = await log_storage.get_logs_range(start, end)
        return logs

    @staticmethod
    async def get_recent_anomalies(log_storage: LogStorageManager, count: int = 10):
        """
        Fetch the most recent anomaly logs using recent_anomalies:list and batch log fetch.
        """
        indices = await log_storage.get_recent_anomalies(count)
        if not indices:
            return []
        # Fetch logs for these indices
        logs = []
        for idx in indices:
            log = await log_storage.get_log(idx)
            if log and log.get("is_anomaly"):
                logs.append(log)
        return logs

def make_group_anomalies_tool(log_storage: LogStorageManager):
    @function_tool
    async def group_anomalies(start_index: int, end_index: int) -> list:
        """Fetch anomalies and group them by resource, type, and proximity."""
        anomalies = await make_get_anomalies_by_index(log_storage)(start_index, end_index)
        return AnomalyGroupingTools.group_anomalies(anomalies)
    return group_anomalies 
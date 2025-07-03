from typing import Generator, Optional
import json
import logging
from contextlib import contextmanager

logger = logging.getLogger("file_utils")

@contextmanager
def safe_open(file_path: str, mode: str = "r"):
    """
    Context manager for safe file opening.
    """
    try:
        f = open(file_path, mode)
        yield f
    except Exception as e:
        logger.error(f"Failed to open file {file_path}: {e}")
        raise
    finally:
        try:
            f.close()
        except Exception:
            pass

def read_file(file_path: str, as_bytes: bool = False) -> str:
    """
    Read file content as text or bytes.
    """
    mode = "rb" if as_bytes else "r"
    with safe_open(file_path, mode) as f:
        return f.read()

def detect_format(file_path: str) -> str:
    """
    Detect log file format: 'json', 'text', 'line-delimited-json', or 'unknown'.
    """
    try:
        with safe_open(file_path, "r") as f:
            first_line = f.readline().strip()
            if first_line.startswith("{") and first_line.endswith("}"):
                # Try to parse as JSON
                try:
                    json.loads(first_line)
                    return "line-delimited-json"
                except Exception:
                    pass
            elif first_line.startswith("["):
                return "json"
            else:
                return "text"
    except Exception as e:
        logger.warning(f"Could not detect format for {file_path}: {e}")
        return "unknown"

def stream_file_lines(file_path: str) -> Generator[str, None, None]:
    """
    Generator for streaming file lines (for large files).
    """
    try:
        with safe_open(file_path, "r") as f:
            for line in f:
                yield line.rstrip("\n")
    except Exception as e:
        logger.error(f"Error streaming file {file_path}: {e}")
        raise 
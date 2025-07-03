import logging
from typing import Any, Optional, Dict
import traceback

logger = logging.getLogger("error_utils")

def log_and_raise(message: str, exc: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
    """
    Log an error and raise an exception.
    """
    if context:
        logger.error(f"{message} | Context: {context}")
    else:
        logger.error(message)
    if exc:
        logger.error(f"Exception: {exc}")
        raise exc
    raise Exception(message)

def log_warning(message: str, context: Optional[Dict[str, Any]] = None):
    """
    Log a warning with optional context.
    """
    if context:
        logger.warning(f"{message} | Context: {context}")
    else:
        logger.warning(message)

def capture_exception(exc: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Capture and log exception details (optionally integrate with Sentry or similar).
    """
    logger.error(f"Exception captured: {exc}")
    if context:
        logger.error(f"Context: {context}")
    logger.error(traceback.format_exc())
    # TODO: Integrate with Sentry or other error tracking if needed

def format_validation_error(field: str, error_type: str, message: str, raw_value: Any) -> Dict[str, Any]:
    """
    Format a validation error for API responses.
    """
    return {
        "field": field,
        "error_type": error_type,
        "message": message,
        "raw_value": raw_value
    } 
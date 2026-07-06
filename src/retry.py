import functools
import logging
import time

logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, base_delay: float = 2.0, exceptions=(Exception,)):
    """Retry decorator with exponential backoff. ponytail: no tenacity dep, few lines does it."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        logger.error("%s failed after %d attempts: %s", fn.__name__, attempt, exc)
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "%s failed (attempt %d/%d): %s. Retrying in %.1fs",
                        fn.__name__, attempt, max_attempts, exc, delay,
                    )
                    time.sleep(delay)
        return wrapper
    return decorator

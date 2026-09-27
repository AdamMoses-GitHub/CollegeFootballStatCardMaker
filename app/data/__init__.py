# data package
import logging

logger = logging.getLogger(__name__)


def api_error(exc: Exception, context: str) -> RuntimeError:
    """Log a cfbd API failure and return a user-facing RuntimeError."""
    if getattr(exc, "status", None) == 429:
        body = getattr(exc, "body", "") or ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        if "quota" in body.lower():
            msg = "CFBD monthly API call quota exceeded. Try again after your quota resets."
        else:
            msg = "CFBD API rate limit hit (too many requests). Wait a moment and try again."
        logger.warning("%s: %s", context, msg)
        err = RuntimeError(msg)
        # Hide the long cfbd traceback; the message says everything the user needs.
        err.__suppress_context__ = True
        return err
    logger.error("%s", context, exc_info=exc)
    err = RuntimeError(f"API error: {exc}")
    err.__cause__ = exc
    return err

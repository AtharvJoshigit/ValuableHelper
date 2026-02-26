# utils/google_exception_mapper.py

import re
import logging
from typing import Optional

from google.api_core import exceptions as google_exceptions

from ..resource_exausted_exception import (
    AIResourceException,
    TokenLimitExhaustedException,
    ModelDailyUsageExhaustedException,
    CreditsExhaustedException,
)

logger = logging.getLogger(__name__)

# ── message-level heuristics (all lowercased for matching) ────────────────── #

_TOKEN_LIMIT_PATTERNS = [
    "token limit",
    "context window",
    "input token",
    "exceeds the maximum",
    "too many tokens",
]

_DAILY_QUOTA_PATTERNS = [
    "daily limit",
    "daily quota",
    "quota exceeded",
    "rate limit",
    "requests per minute",
    "requests per day",
    "quota for",
]

_CREDITS_PATTERNS = [
    "billing",
    "credit",
    "insufficient fund",
    "payment",
    "out of budget",
]

# ── helpers ───────────────────────────────────────────────────────────────── #

def _msg(exc: Exception) -> str:
    return str(exc).lower()


def _matches(text: str, patterns: list[str]) -> bool:
    return any(p in text for p in patterns)


def _parse_token_counts(text: str) -> tuple[int, int]:
    """
    Best-effort extraction of (used, limit) from error messages like:
    'Request exceeds the model's input token limit: 200000 > 128000'
    Returns (0, 0) if nothing found.
    """
    numbers = re.findall(r"\b(\d+)\b", text)
    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])
    return 0, 0


def _parse_quota_counts(text: str) -> tuple[int, int]:
    """Extract (used, limit) from quota exhaustion messages."""
    numbers = re.findall(r"\b(\d+)\b", text)
    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])
    return 0, 0


# ── core mapper ───────────────────────────────────────────────────────────── #

def map_google_exception(
    exc: Exception,
    *,
    model: Optional[str] = None,
    phase: Optional[str] = None,
) -> AIResourceException:
    """
    Translate a google.api_core exception into the appropriate
    domain-specific AIResourceException subclass.

    Usage:
        try:
            response = await client.generate_content(...)
        except Exception as e:
            raise map_google_exception(e, model=model_name, phase="generation") from e
    """
    msg = _msg(exc)

    # ── 400: INVALID_ARGUMENT / FAILED_PRECONDITION ───────────────────────── #
    if isinstance(exc, (google_exceptions.InvalidArgument,
                        google_exceptions.FailedPrecondition)):
        if _matches(msg, _TOKEN_LIMIT_PATTERNS):
            used, limit = _parse_token_counts(msg)
            logger.warning(
                "Token limit exceeded (used=%d, limit=%d, phase=%s, model=%s)",
                used, limit, phase, model,
            )
            return TokenLimitExhaustedException(
                used_tokens=used,
                max_tokens=limit,
                phase=phase,
                model=model,
            )
        # Generic bad request (policy block, malformed input, etc.)
        return AIResourceException(
            f"Invalid request rejected by Vertex AI: {exc}",
            model=model,
            details={"google_error_code": "INVALID_ARGUMENT", "raw": str(exc)},
        )

    # ── 429: RESOURCE_EXHAUSTED ───────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.ResourceExhausted):
        # Credits / billing exhaustion check first (subset of 429 responses)
        if _matches(msg, _CREDITS_PATTERNS):
            logger.error("Account credits exhausted: %s", exc)
            return CreditsExhaustedException(
                remaining=0.0,
                required=0.0,  # Google doesn't expose these — caller can enrich
            )
        # Daily quota / rate limit
        used, limit = _parse_quota_counts(msg)
        logger.warning(
            "Quota/rate limit hit (used=%d, limit=%d, model=%s): %s",
            used, limit, model, exc,
        )
        return ModelDailyUsageExhaustedException(
            used=used,
            limit=limit,
            reset_time=None,   # Google doesn't return reset time in the error body
            model=model,
        )

    # ── 403: PERMISSION_DENIED ────────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.PermissionDenied):
        logger.error("Permission denied by Vertex AI (model=%s): %s", model, exc)
        return AIResourceException(
            f"Permission denied: {exc}",
            model=model,
            details={"google_error_code": "PERMISSION_DENIED", "raw": str(exc)},
        )

    # ── 404: NOT_FOUND ────────────────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.NotFound):
        logger.error("Resource not found on Vertex AI (model=%s): %s", model, exc)
        return AIResourceException(
            f"Resource not found: {exc}",
            model=model,
            details={"google_error_code": "NOT_FOUND", "raw": str(exc)},
        )

    # ── 499: CANCELLED ────────────────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.Cancelled):
        logger.warning("Request cancelled by client (model=%s): %s", model, exc)
        return AIResourceException(
            f"Request cancelled: {exc}",
            model=model,
            details={"google_error_code": "CANCELLED", "raw": str(exc)},
        )

    # ── 504: DEADLINE_EXCEEDED ────────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.DeadlineExceeded):
        logger.error("Deadline exceeded on Vertex AI (model=%s): %s", model, exc)
        return AIResourceException(
            f"Request timed out (deadline exceeded): {exc}",
            model=model,
            details={"google_error_code": "DEADLINE_EXCEEDED", "raw": str(exc)},
        )

    # ── 503: UNAVAILABLE ─────────────────────────────────────────────────── #
    if isinstance(exc, google_exceptions.ServiceUnavailable):
        logger.error("Vertex AI temporarily unavailable (model=%s): %s", model, exc)
        return AIResourceException(
            f"Service temporarily unavailable: {exc}",
            model=model,
            details={"google_error_code": "UNAVAILABLE", "raw": str(exc)},
        )

    # ── 500: INTERNAL / UNKNOWN ───────────────────────────────────────────── #
    if isinstance(exc, (google_exceptions.InternalServerError,
                        google_exceptions.Unknown)):
        logger.error("Internal Vertex AI server error (model=%s): %s", model, exc)
        return AIResourceException(
            f"Internal server error from Vertex AI: {exc}",
            model=model,
            details={"google_error_code": "INTERNAL", "raw": str(exc)},
        )

    # ── Fallback: unknown google exception ───────────────────────────────── #
    logger.error("Unmapped Google API exception (model=%s): %s", model, exc)
    return AIResourceException(
        f"Unexpected Vertex AI error: {exc}",
        model=model,
        details={"raw": str(exc)},
    )
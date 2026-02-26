class AIResourceException(Exception):
    """Base class for AI resource-related failures."""
    
    def __init__(self, message: str, *, model: str = None, details: dict = None):
        super().__init__(message)
        self.model = model
        self.details = details or {}


class TokenLimitExhaustedException(AIResourceException):
    """Raised when context window token limit is exceeded."""
    
    def __init__(
        self,
        *,
        used_tokens: int,
        max_tokens: int,
        phase: str = None,  # e.g. 'reasoning', 'history_load', 'generation'
        model: str = None,
    ):
        message = (
            f"Token limit exhausted: {used_tokens}/{max_tokens} tokens used."
        )
        super().__init__(
            message,
            model=model,
            details={
                "used_tokens": used_tokens,
                "max_tokens": max_tokens,
                "phase": phase,
            },
        )
        self.used_tokens = used_tokens
        self.max_tokens = max_tokens
        self.phase = phase


class ModelDailyUsageExhaustedException(AIResourceException):
    """Raised when model daily usage quota is exceeded."""
    
    def __init__(
        self,
        *,
        used: int,
        limit: int,
        reset_time: str = None,
        model: str = None,
    ):
        message = f"Daily model usage exhausted: {used}/{limit}."
        super().__init__(
            message,
            model=model,
            details={
                "used": used,
                "limit": limit,
                "reset_time": reset_time,
            },
        )
        self.used = used
        self.limit = limit
        self.reset_time = reset_time


class CreditsExhaustedException(AIResourceException):
    """Raised when account credits are depleted."""
    
    def __init__(
        self,
        *,
        remaining: float,
        required: float,
    ):
        message = (
            f"Insufficient credits: {remaining} remaining, "
            f"{required} required."
        )
        super().__init__(
            message,
            details={
                "remaining": remaining,
                "required": required,
            },
        )
        self.remaining = remaining
        self.required = required
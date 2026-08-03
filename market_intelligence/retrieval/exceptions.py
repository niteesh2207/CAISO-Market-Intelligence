from __future__ import annotations


class RetrievalError(RuntimeError):
    """Base retrieval exception."""


class SourceUnavailableError(RetrievalError):
    """Source is temporarily or permanently unavailable."""


class SourceUnauthorizedError(RetrievalError):
    """Source requires credentials or authorization."""


class SourceRateLimitedError(RetrievalError):
    """Source rejected the request due to rate limiting."""


class SourceResponseError(RetrievalError):
    """Source returned an invalid or unusable response."""

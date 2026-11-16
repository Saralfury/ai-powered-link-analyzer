"""Custom exceptions with consistent error codes and HTTP status mapping."""

from typing import Any, Dict, Optional


class LinkAnalysisError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class InvalidURLError(LinkAnalysisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, "INVALID_URL", 422, details)


class SSRFError(LinkAnalysisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, "BLOCKED_DESTINATION", 400, details)


class ExtractionError(LinkAnalysisError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, "EXTRACTION_FAILED", 502, details)


class LLMError(LinkAnalysisError):
    def __init__(
        self,
        message: str,
        error_code: str = "LLM_FAILED",
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, error_code, status_code, details)

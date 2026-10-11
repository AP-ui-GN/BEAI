"""Typed domain errors. Routes and services raise these; handlers map them to HTTP."""


class BeaiError(Exception):
    """Base class for errors that have a stable client-facing code and status."""

    status_code = 500
    code = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInput(BeaiError):
    """The upload or request content is not a usable structure."""

    status_code = 422
    code = "invalid_input"


class NotFound(BeaiError):
    """The requested row does not exist."""

    status_code = 404
    code = "not_found"


class ExternalServiceError(BeaiError):
    """An upstream service failed. Callers must not invent a record."""

    status_code = 502
    code = "external_service_error"


class CapabilityUnavailable(BeaiError):
    """An optional scientific tool is not installed or not usable."""

    status_code = 503
    code = "capability_unavailable"


class PayloadTooLarge(BeaiError):
    """The upload exceeded the configured byte limit while streaming."""

    status_code = 413
    code = "payload_too_large"

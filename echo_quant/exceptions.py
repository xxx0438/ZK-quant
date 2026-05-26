"""SDK-specific exceptions. Caught by CLI for clean error messages."""

class EchoError(Exception):
    """Base SDK exception."""

class ValidationError(EchoError):
    """Raised by `echo-cli validate` when a model fails interface checks."""

class BacktestError(EchoError):
    """Raised when a backtest cannot run (missing data, etc.)."""

class PackagingError(EchoError):
    """Raised during ONNX export or kit assembly."""

class ApiError(EchoError):
    """Raised by the API client on HTTP errors."""

    def __init__(self, status: int, code: str, message: str, hint: str | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"[{code}] {message}" + (f" — {hint}" if hint else ""))

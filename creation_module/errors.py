"""Domain errors raised by the controlled Creation Module workflow."""


class CreationModuleError(Exception):
    """Base error for creation operations."""


class SourceNotFoundError(CreationModuleError):
    """Raised when a registered source cannot be found."""


class SourceChangedError(CreationModuleError):
    """Raised when output was generated from an older source version."""


class ValidationError(CreationModuleError):
    """Raised when generated structured output is invalid."""


class ApprovalError(CreationModuleError):
    """Raised when an approval request names unknown proposals."""

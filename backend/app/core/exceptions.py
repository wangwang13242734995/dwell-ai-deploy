"""
Custom Exceptions

Application-specific exceptions for error handling.
"""

from typing import Optional, List


class PocketPlannerError(Exception):
    """Base exception for Pocket Planner application."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class VisionExtractionError(PocketPlannerError):
    """Raised when Gemini vision analysis fails."""
    
    def __init__(self, message: str = "Failed to extract objects from image"):
        super().__init__(message, error_code="VISION_EXTRACTION_FAILED")


class ConstraintViolationError(PocketPlannerError):
    """Raised when layout constraints cannot be satisfied."""
    
    def __init__(
        self, 
        message: str = "Layout constraints violated",
        violations: Optional[List[str]] = None
    ):
        self.violations = violations or []
        super().__init__(message, error_code="CONSTRAINT_VIOLATION")


class RenderingError(PocketPlannerError):
    """Raised when image rendering/editing fails."""
    
    def __init__(self, message: str = "Failed to render edited image"):
        super().__init__(message, error_code="RENDERING_FAILED")


class InvalidImageError(PocketPlannerError):
    """Raised when an invalid or corrupted image is provided."""
    
    def __init__(self, message: str = "Invalid or corrupted image data"):
        super().__init__(message, error_code="INVALID_IMAGE")


class ConfigurationError(PocketPlannerError):
    """Raised when required configuration is missing."""
    
    def __init__(self, message: str = "Missing required configuration"):
        super().__init__(message, error_code="CONFIGURATION_ERROR")


class OptimizationError(PocketPlannerError):
    """Raised when layout optimization fails."""
    
    def __init__(self, message: str = "Layout optimization failed"):
        super().__init__(message, error_code="OPTIMIZATION_FAILED")

"""Custom exceptions for the documentary renderer."""


class DocumentaryRendererError(Exception):
    """Base exception for renderer failures."""


class StoryboardParseError(DocumentaryRendererError):
    """Raised when a storyboard cannot be read or decoded."""


class ValidationError(DocumentaryRendererError):
    """Raised when a storyboard contains invalid values."""


class FFmpegError(DocumentaryRendererError):
    """Raised when FFmpeg or FFprobe fails."""

# -*- coding: utf-8 -*-
"""
Custom exceptions for Framecut

Define application-specific exceptions.
"""

class FramecutError(Exception):
    """Base exception for all Framecut errors"""
    pass

class DeviceError(FramecutError):
    """Errors related to device detection or compatibility"""
    pass

class ProfileError(FramecutError):
    """Errors related to color profile detection or compatibility"""
    pass

class ExtractionError(FramecutError):
    """Errors during frame extraction process"""
    pass

class MetadataError(FramecutError):
    """Errors during metadata processing"""
    pass

class FileNotFoundError(FramecutError):
    """Input or reference files not found"""
    pass

class CommandExecutionError(FramecutError):
    """Errors during external command execution (ffmpeg, exiftool)"""
    pass 
# -*- coding: utf-8 -*-
"""
Utility functions for Framecut

General purpose utility functions used throughout the application.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from framecut.exceptions import CommandExecutionError

# Configure logging
class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emoji to log messages"""
    
    def format(self, record):
        # Add emoji to message for different log levels
        if record.levelno == logging.ERROR:
            record.msg = f"❌ {record.msg}"
        return super().format(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('framecut')

# Apply custom formatter to all handlers
for handler in logger.handlers or logging.getLogger().handlers:
    handler.setFormatter(EmojiFormatter('%(asctime)s - %(levelname)s - %(message)s', 
                                        datefmt='%Y-%m-%d %H:%M:%S'))

def parse_timestamp(timestamp: str) -> float:
    """
    Convert timestamp string (00:00:00.000) to seconds (float)
    
    Args:
        timestamp: Timestamp in format HH:MM:SS.mmm
        
    Returns:
        Timestamp in seconds as float
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        h, m, sm = timestamp.split(':')
        s, ms = sm.replace(',', '.').split('.')
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000
    except ValueError as e:
        logger.error(f"Invalid timestamp format: {timestamp}")
        raise ValueError(f"Invalid timestamp format: {timestamp}. Expected format: HH:MM:SS.mmm") from e

def format_timestamp_for_filename(timestamp: str) -> str:
    """
    Convert timestamp string (00:00:00.000) to filename-friendly format (000000.000)
    
    Args:
        timestamp: Timestamp in format HH:MM:SS.mmm
        
    Returns:
        Filename-friendly timestamp format
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        h, m, sm = timestamp.split(':')
        s, ms = sm.replace(',', '.').split('.')
        return f"{int(h):02d}{int(m):02d}{int(s):02d}.{ms}"
    except ValueError as e:
        logger.error(f"Invalid timestamp format: {timestamp}")
        raise ValueError(f"Invalid timestamp format: {timestamp}. Expected format: HH:MM:SS.mmm") from e

def merge_ffmpeg_params(base_params: List[str], override_params: Optional[List[str]]) -> List[str]:
    """
    Properly merge base FFmpeg parameters with override parameters
    
    Note: This function is kept for backwards compatibility.
    In the new architecture, use device_settings.get_device_ffmpeg_params() instead.
    
    Args:
        base_params: Base FFmpeg parameters
        override_params: Parameters to override base params
        
    Returns:
        Merged parameters with overrides applied
    """
    if not override_params:
        return base_params.copy()
        
    # Create a dictionary to track parameters that we might need to override
    param_dict: Dict[str, str] = {}
    
    # First pass: convert list of args to a dict for easier override
    for i in range(0, len(base_params), 2):
        if i + 1 < len(base_params):  # Make sure we have a value for this key
            param_dict[base_params[i]] = base_params[i + 1]
    
    # Second pass: override with profile params
    for i in range(0, len(override_params), 2):
        if i + 1 < len(override_params):  # Make sure we have a value for this key
            param_name = override_params[i]
            param_value = override_params[i + 1]
            param_dict[param_name] = param_value
            logger.debug(f"Overriding {param_name} with value {param_value}")
    
    # Convert back to flat list for ffmpeg
    result_params: List[str] = []
    for param_name, param_value in param_dict.items():
        result_params.extend([param_name, param_value])
        
    return result_params

def run_command(cmd: List[Union[str, Path]], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """
    Run a shell command and handle errors
    
    Args:
        cmd: Command to run (list of arguments)
        check: Whether to check for errors
        capture_output: Whether to capture output
        
    Returns:
        Result of the command
        
    Raises:
        CommandExecutionError: If command execution fails
    """
    # Convert any Path objects to strings
    cmd_str = [str(arg) for arg in cmd]
    
    logger.debug(f"Running command: {' '.join(cmd_str)}")
    try:
        result = subprocess.run(cmd_str, check=check, capture_output=capture_output, text=True)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"STDERR: {e.stderr}")
        raise CommandExecutionError(f"Command execution failed: {e.stderr}") from e 
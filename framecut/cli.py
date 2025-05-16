# -*- coding: utf-8 -*-
"""
Command Line Interface module for Framecut

Handles command-line argument parsing and CLI functionality.
"""

import sys
import argparse
from argparse import Namespace
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import textwrap

from framecut.utils import logger
from framecut.enums import ColorProfile, DeviceType
from framecut.device_settings import device_manager


def parse_arguments(args: Optional[List[str]] = None) -> Namespace:
    """
    Parse command line arguments for Framecut
    
    Args:
        args: Command line arguments (uses sys.argv if None)
        
    Returns:
        Parsed arguments namespace
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Extract a frame from a DJI video with precise timing and metadata preservation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # Extract a frame at 1 minute 23.5 seconds 
          framecut video.MP4 00:01:23.500
          
          # Specify the device model and color profile
          framecut video.MP4 00:01:23.500 --device "DJI Mini 3 Pro" --profile d_cinelike
          
          # Extract multiple frames using bracketing (one at timestamp, one before and one after)
          framecut video.MP4 00:01:23.500 -b
          
          # Customize bracketing with 2 frames on each side and custom interval
          framecut video.MP4 00:01:23.500 -b -f 2 -i 00:00:00.500
        """)
    )
    
    # Positional arguments
    parser.add_argument("input", help="Video file")
    parser.add_argument("timestamp", help="Timestamp in format HH:MM:SS.mmm")
    
    # Optional arguments
    parser.add_argument("-o", "--output", 
                      help="Output directory (default: same as video)")
    parser.add_argument("-d", "--device", 
                      help="Force specific device model (e.g., " + 
                           '"DJI Mini 3 Pro", "DJI Mavic 2 Pro", "DJI Osmo Action 5 Pro")')
    parser.add_argument("-p", "--profile", choices=ColorProfile.get_all_profiles(),
                      help="Force specific color profile (" + 
                           ", ".join(ColorProfile.get_all_profiles()) + ")")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable verbose output")
                      
    # Bracketing options
    bracketing_group = parser.add_argument_group('bracketing options')
    bracketing_group.add_argument("-b", "--bracketing", action="store_true",
                      help="Enable bracketing mode to extract multiple frames around the specified timestamp")
    bracketing_group.add_argument("-f", "--bracket-frames", type=int, default=1,
                      help="Number of additional frames on each side in bracketing mode (default: 1)")
    bracketing_group.add_argument("-i", "--bracket-interval", default="00:00:00.250",
                      help="Time interval between bracketed frames in format HH:MM:SS.mmm (default: 00:00:00.250)")
    
    return parser.parse_args(args)


def configure_logging(verbose: bool) -> None:
    """
    Configure logging level based on verbose flag
    
    Args:
        verbose: Whether to use verbose (debug) logging
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled") 
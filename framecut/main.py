# -*- coding: utf-8 -*-
"""
Main module for Framecut

The main entry point and core logic for the framecut program.
"""

import sys
import os
from pathlib import Path

from framecut.utils import logger
from framecut.cli import parse_arguments, configure_logging
from framecut.framecut import framecut
from framecut.exceptions import FramecutError, DeviceError, ProfileError


def main():
    """
    Main function for framecut.py
    """
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Configure verbose logging if requested
    configure_logging(args.verbose)
    
    # Convert to Path and validate input
    input_path = Path(args.input)
    
    # Check if input is a file
    if input_path.is_file():
        # Process single video file with single timestamp
        try:
            process_video(
                input_path,
                args.timestamp, 
                args.output,
                args.device,
                args.profile,
                args.bracketing,
                args.bracket_frames,
                args.bracket_interval
            )
            return 0
        except Exception as e:
            handle_exception(e)
    else:
        logger.error(f"Input must be a video file: {input_path}")
        sys.exit(f"Error: Input must be a video file: {input_path}")


def process_video(video_path, timestamp, output_dir=None, device_type=None, color_profile=None,
                 bracketing=False, bracket_frames=1, bracket_interval="00:00:00.250"):
    """Process a single video file with a single timestamp"""
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        sys.exit(f"Error: Video file not found: {video_path}")
            
    # Create output directory if specified
    if output_dir:
        output_dir = Path(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
    try:
        # Extract frame for the timestamp
        files = framecut.process_video(
            video_path=video_path,
            timestamp=timestamp,
            device_type=device_type,
            color_profile=color_profile,
            output_dir=output_dir,
            bracketing=bracketing,
            bracket_frames=bracket_frames,
            bracket_interval=bracket_interval
        )
        
        logger.debug(f"Successfully processed {'frames' if bracketing else 'frame'} from {video_path}")
        return files
    except DeviceError:
        # Don't log the error here, it's already logged where raised
        raise
    except Exception as e:
        logger.error(f"Error processing timestamp {timestamp}: {e}")
        raise


def handle_exception(exception):
    """Handle exceptions with appropriate error messages"""
    if isinstance(exception, DeviceError):
        # The error is already logged where it was raised
        sys.exit(f"Error: {exception}")
    elif isinstance(exception, ProfileError):
        logger.error(f"Profile error: {exception}")
        sys.exit(f"Error: {exception}")
    elif isinstance(exception, FramecutError):
        logger.error(f"Error during frame extraction: {exception}")
        sys.exit(f"Error: {exception}")
    else:
        logger.error(f"Unexpected error: {exception}", exc_info=True)
        sys.exit(f"An unexpected error occurred: {exception}")


if __name__ == "__main__":
    main() 
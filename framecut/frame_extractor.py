# -*- coding: utf-8 -*-
"""
Frame extraction module for Framecut

Functions for extracting frames from video files.
"""

from pathlib import Path
import subprocess
from typing import List, Dict, Any, Optional, Union, Tuple

from framecut.utils import logger, parse_timestamp, run_command
from framecut.exceptions import ExtractionError


class FrameExtractor:
    """Handles extraction of frames from video files"""
    
    def extract_frame(
        self, 
        video_path: Union[str, Path], 
        timestamp: str, 
        output_path: Union[str, Path], 
        ffmpeg_params: List[str]
    ) -> bool:
        """
        Extract a single frame from the video at the specified timestamp
        
        Args:
            video_path: Path to video file
            timestamp: Timestamp to extract (00:00:00.000)
            output_path: Path to save extracted frame
            ffmpeg_params: FFmpeg parameters for frame extraction
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ExtractionError: If frame extraction fails
        """
        try:
            video_path = Path(video_path)
            output_path = Path(output_path)
            
            logger.debug(f"Extracting frame at {timestamp} to {output_path}...")
            
            # Make sure output directory exists
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            cmd = [
                "ffmpeg",
                "-y",             # Overwrite output files without asking
                "-ss", timestamp, # Seek to timestamp (placing before -i for faster seeking)
                "-i", video_path, # Input file
                *ffmpeg_params,   # Device-specific settings
                "-frames:v", "1", # Extract one frame
                output_path
            ]
            
            # We don't log the command here, it will be logged in run_command
            run_command(cmd)
            
            # Add informational message with successful extraction details
            logger.info(f"✓ Frame extracted to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error extracting frame at {timestamp}: {e}...")
            raise ExtractionError(f"Failed to extract frame at {timestamp}: {str(e)}") from e


# Create a singleton instance for global use
frame_extractor = FrameExtractor() 
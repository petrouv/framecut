# -*- coding: utf-8 -*-
"""
Main processor class for Framecut

Central class that orchestrates the video frame extraction process based on timestamps.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import os

from framecut.utils import logger, format_timestamp_for_filename
from framecut.enums import DeviceType, ColorProfile
from framecut.device_settings import device_manager
from framecut.color_profiles import profile_manager
from framecut.metadata_processor import metadata_processor
from framecut.video_analyzer import video_analyzer
from framecut.frame_extractor import frame_extractor
from framecut.exceptions import FramecutError, DeviceError, ProfileError


class Framecut:
    """Main class for orchestrating the frame extraction process from videos"""
    
    def __init__(self):
        """Initialize Framecut instance with all required components"""
        self.device_manager = device_manager
        self.profile_manager = profile_manager
        self.metadata_processor = metadata_processor
        self.video_analyzer = video_analyzer
        self.frame_extractor = frame_extractor
    
    def process_video(
        self,
        video_path: Union[str, Path],
        timestamp: str,
        device_type: Optional[str] = None,
        color_profile: Optional[str] = None,
        output_dir: Optional[Union[str, Path]] = None,
        bracketing: bool = False,
        bracket_frames: int = 1,
        bracket_interval: str = "00:00:00.250"
    ) -> List[Tuple[str, Path]]:
        """
        Process a video file to extract frames at specified timestamps
        
        Args:
            video_path: Path to video file
            timestamp: Timestamp to extract in format HH:MM:SS.mmm (00:00:00.000)
            device_type: Device type (auto-detected if not specified)
            color_profile: Color profile (auto-detected if not specified)
            output_dir: Output directory (defaults to video location)
            bracketing: Whether to enable bracketing mode (extract multiple frames around target timestamp)
            bracket_frames: Number of additional frames to extract on each side in bracketing mode
            bracket_interval: Time interval between bracketed frames (00:00:00.000)
            
        Returns:
            List of (timestamp, output_path) tuples for all extracted frames
            
        Raises:
            FramecutError: If the video processing fails
            DeviceError: If the device type cannot be determined
            ProfileError: If the color profile is not supported for the device
        """
        try:
            video_path = Path(video_path).resolve()
            
            # Create output directory if not provided
            if not output_dir:
                output_dir = video_path.parent
            output_dir = Path(output_dir).resolve()
            output_dir.mkdir(exist_ok=True, parents=True)
            
            # Handle explicitly provided color profile
            if color_profile:
                logger.debug(f"Using user-specified color profile: {color_profile}")
            
            # Device type detection logic
            if device_type:
                logger.debug(f"Using user-specified device: {device_type}")
            else:
                # Only auto-detect device if not specified by user
                logger.debug("Auto-detecting device type...")
                
                # Skip profile detection if color profile was specified by user
                if color_profile:
                    # We need to detect only device type, not profile
                    detected_device = self.video_analyzer.detect_device_type(video_path)
                    device_type = detected_device
                else:
                    # Detect both device and profile
                    detected_device, detected_profile = self.video_analyzer.detect_device_from_video(video_path)
                    device_type = detected_device
                    
                    # Use detected profile if one was found
                    if detected_profile:
                        color_profile = detected_profile
                        logger.debug(f"Using auto-detected profile: {color_profile}")
                
                # If device was still not detected, raise error
                if not device_type:
                    logger.error("Unable to determine device type. Please specify with --device.")
                    raise DeviceError("Unable to determine device type. Please specify with --device.")
                
                logger.debug(f"Using auto-detected device: {device_type}")
            
            # If color profile still not determined, try to detect it now
            if not color_profile:
                logger.debug(f"Auto-detecting color profile for specified device: {device_type}...")
                color_profile = self.video_analyzer.detect_color_profile(video_path, device_type)
            
            # Validate that color profile is supported for this device
            if color_profile not in self.device_manager.get_supported_profiles(device_type):
                logger.error(f"Color profile '{color_profile}' is not supported for device {device_type}.")
                supported_profiles = self.device_manager.get_supported_profiles(device_type)
                raise ProfileError(
                    f"Color profile '{color_profile}' is not supported for device {device_type}. "
                    f"Supported profiles: {', '.join(supported_profiles)}"
                )
            
            logger.info(f"Using device settings for: {device_type}, color profile: {color_profile}")
            
            # Get FFmpeg parameters specific to the device and profile
            device_settings = self.device_manager.get_device_ffmpeg_params(device_type, color_profile)
            
            logger.debug(f"Final device-specific ffmpeg parameters: {device_settings}")
            
            # Generate timestamps based on bracketing options
            timestamps = [timestamp]
            if bracketing:
                from datetime import datetime, timedelta
                
                # Parse the base timestamp and interval
                base_time_format = "%H:%M:%S.%f"
                base_time = datetime.strptime(timestamp, base_time_format)
                interval = datetime.strptime(bracket_interval, base_time_format)
                interval_seconds = interval.hour * 3600 + interval.minute * 60 + interval.second + interval.microsecond / 1000000
                
                # Generate timestamps before the specified time
                for i in range(1, bracket_frames + 1):
                    offset = timedelta(seconds=interval_seconds * i)
                    before_time = base_time - offset
                    before_timestamp = before_time.strftime(base_time_format)[:-3]  # Truncate microseconds to milliseconds
                    timestamps.insert(0, before_timestamp)
                
                # Generate timestamps after the specified time
                for i in range(1, bracket_frames + 1):
                    offset = timedelta(seconds=interval_seconds * i)
                    after_time = base_time + offset
                    after_timestamp = after_time.strftime(base_time_format)[:-3]  # Truncate microseconds to milliseconds
                    timestamps.append(after_timestamp)
            
            # Process each timestamp and extract the corresponding frame
            extracted_files = []
            for timestamp in timestamps:
                # Generate output filename with timestamp
                filename_timestamp = format_timestamp_for_filename(timestamp)
                output_filename = f"{video_path.stem}-{filename_timestamp}.tiff"
                output_path = output_dir / output_filename
                
                # Extract the frame at this timestamp
                success = self.frame_extractor.extract_frame(video_path, timestamp, output_path, device_settings)
                
                extracted_files.append((timestamp, output_path))
            
            # Look for SRT subtitle file with the same name as the video for metadata extraction
            srt_path = self.metadata_processor.find_matching_srt(video_path)
            
            # Process metadata for each extracted frame
            for timestamp, tiff_path in extracted_files:
                # Try to get metadata from SRT file first as it often contains telemetry data
                telemetry = None
                if srt_path:
                    telemetry = self.metadata_processor.find_srt_telemetry(srt_path, timestamp)
                
                # If no SRT metadata found, try extracting from video directly
                if not telemetry:
                    telemetry = self.metadata_processor.extract_metadata_from_video(video_path)
                
                # Write metadata to TIFF file if available
                if telemetry:
                    self.metadata_processor.write_exif_metadata(tiff_path, telemetry, device_type)
                else:
                    logger.warning(f"✗ No metadata available for {tiff_path}")
            
            return extracted_files
        except DeviceError as e:
            # Re-raise DeviceError directly without wrapping
            raise
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            raise FramecutError("Error processing video. Please check the logs for more details.")


# Create a singleton instance for global use
framecut = Framecut() 
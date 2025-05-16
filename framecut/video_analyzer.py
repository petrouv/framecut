# -*- coding: utf-8 -*-
"""
Video analysis module for Framecut

Module for comprehensive analysis of video files to detect:
- Device models (including DJI cameras and other supported devices)
- Color profiles (Normal, D-Cinelike, D-Log, HLG)
- Bit depth and pixel formats
- Video statistics and characteristics
"""

import json
import statistics
import tempfile
import pathlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List, Any, Union, Set
import os
import re
import logging

from framecut.utils import logger, run_command
from framecut.enums import DeviceType, ColorProfile
from framecut.device_settings import device_manager
from framecut.color_profiles import profile_manager
from framecut.exceptions import DeviceError, ProfileError, CommandExecutionError


# Maximum saturation value for normalization
MAX_SAT: float = 1.0


@dataclass
class VideoStats:
    """Statistics about a video frame sample"""
    p90y: float  # Upper 10% luminance (0-1023 in 10-bit)
    satavg: float  # Average saturation (0-~70 in 4:2:0)
    yavg: float  # Average luminance


@dataclass
class VideoMetadata:
    """Metadata from video container"""
    color_primaries: Optional[str] = None  # e.g., "bt709", "bt2020"
    color_transfer: Optional[str] = None   # e.g., "bt709", "arib-std-b67" (HLG), "smpte2084" (PQ/HDR10), "log"
    color_space: Optional[str] = None      # e.g., "bt709", "bt2020nc"
    dji_color_mode: Optional[str] = None   # DJI's private tag, if available


class VideoAnalyzer:
    """Analyzes video files to determine device type and color profile"""
    
    def __init__(self):
        """Initialize analyzer with an empty cache for video properties"""
        self._properties_cache = {}  # Cache for video properties by file path
    
    def detect_device_from_video(self, video_path: Union[str, pathlib.Path]) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect the device type and color profile from video metadata using exiftool
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (device_type, color_profile)
            
        Raises:
            CommandExecutionError: If there is an error executing exiftool
        """
        try:
            video_path = pathlib.Path(video_path)
            
            # Get video metadata using exiftool
            cmd = ["exiftool", "-j", video_path]
            result = run_command(cmd)
            metadata = json.loads(result.stdout)
            
            if not metadata:
                logger.warning("No metadata found in video file")
                return None, None
                
            metadata = metadata[0]  # exiftool returns a list with one element
            
            # Log some of the key metadata fields for debugging
            logger.debug(f"File: {metadata.get('FileName', 'Unknown')}")
            logger.debug(f"Make: {metadata.get('Make', 'Unknown')}")
            logger.debug(f"Model: {metadata.get('Model', 'Unknown')}")
            logger.debug(f"Encoder: {metadata.get('Encoder', 'Unknown')}")
            logger.debug(f"Created: {metadata.get('CreateDate', 'Unknown')}")
            
            # Check for device information in various metadata fields
            make = metadata.get("Make", "")
            model = metadata.get("Model", "")
            encoder = metadata.get("Encoder", "")
            
            # Detect device type
            device_type = None
            if "DJI Mini 3 Pro" in model or "Mini 3 Pro" in encoder:
                device_type = DeviceType.MINI_3_PRO.value
            elif "Mavic 2 Pro" in model or "Mavic 2 Pro" in encoder:
                device_type = DeviceType.MAVIC_2_PRO.value
            elif "OsmoAction5 Pro" in encoder or "Osmo Action 5 Pro" in encoder or "Action 5" in model:
                device_type = DeviceType.ACTION_5_PRO.value
                
            if device_type:
                logger.debug(f"Detected device: {device_type}")
            else:
                # Improve warning message by replacing empty values with "N/A"
                make_str = make if make else "N/A"
                model_str = model if model else "N/A"
                encoder_str = encoder if encoder else "N/A"
                logger.warning(f"Unknown device type. Make: {make_str}, Model: {model_str}, Encoder: {encoder_str}")
                # Return immediately when no device is detected
                return None, None
            
            # Use the comprehensive profile detection function
            color_profile, profile_source = self.detect_color_profile_from_all_sources(
                video_path=video_path,
                device_type=device_type,
                metadata=metadata
            )
            
            return device_type, color_profile
            
        except Exception as e:
            logger.error(f"Error detecting device: {e}", exc_info=True)
            return None, None

    def get_video_properties(self, video_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
        """
        Get all relevant video properties in a single ffprobe call, with caching
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video properties (pix_fmt, color metadata, frame rate, duration)
            
        Raises:
            CommandExecutionError: If there is an error executing ffprobe
        """
        video_path = pathlib.Path(video_path)
        path_str = str(video_path)
        
        # If properties are already in cache, return them
        if path_str in self._properties_cache:
            return self._properties_cache[path_str]
        
        cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "v:0",
            "-show_entries", "stream=pix_fmt,color_primaries,color_transfer,color_space,r_frame_rate:format=duration", 
            "-of", "json", 
            str(video_path)
        ]
        
        properties = {
            "pix_fmt": "yuv420p",
            "color_primaries": None,
            "color_transfer": None,
            "color_space": None,
            "r_frame_rate": "30/1",
            "fps": 30.0,
            "duration": 0.0
        }
        
        try:
            result = run_command(cmd)
            data = json.loads(result.stdout)
            
            # Get stream properties
            if "streams" in data and len(data["streams"]) > 0:
                stream = data["streams"][0]
                if "pix_fmt" in stream:
                    properties["pix_fmt"] = stream["pix_fmt"]
                    logger.debug(f"Pixel format: {properties['pix_fmt']}")
                
                if "color_primaries" in stream:
                    properties["color_primaries"] = stream["color_primaries"]
                
                if "color_transfer" in stream:
                    properties["color_transfer"] = stream["color_transfer"]
                
                if "color_space" in stream:
                    properties["color_space"] = stream["color_space"]
                
                if "r_frame_rate" in stream:
                    properties["r_frame_rate"] = stream["r_frame_rate"]
                    # Calculate actual FPS
                    num, denom = map(int, properties["r_frame_rate"].split('/'))
                    properties["fps"] = num / denom if denom != 0 else 30.0
                    logger.debug(f"Frame rate: {properties['fps']} FPS")
            
            # Get format properties
            if "format" in data and "duration" in data["format"]:
                properties["duration"] = float(data["format"]["duration"])
                logger.debug(f"Video duration: {properties['duration']:.2f}s")
            
            # Log color metadata
            logger.debug(f"Detected color metadata: primaries={properties['color_primaries']}, "
                        f"transfer={properties['color_transfer']}, space={properties['color_space']}")
            
            # Save result to cache
            self._properties_cache[path_str] = properties
            
            return properties
        except Exception as e:
            logger.error(f"Error determining video properties: {e}")
            return properties

    def get_pixel_format(self, video_path: Union[str, pathlib.Path]) -> str:
        """
        Get the pixel format of a video file
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Pixel format string (e.g., 'yuv420p', 'yuv420p10le')
            
        Raises:
            CommandExecutionError: If there is an error executing ffprobe
        """
        try:
            properties = self.get_video_properties(video_path)
            return properties["pix_fmt"]
        except Exception as e:
            logger.error(f"Error determining pixel format: {e}")
            return "unknown"

    def get_video_metadata(self, video_path: Union[str, pathlib.Path]) -> VideoMetadata:
        """
        Get color metadata from video container
        
        Args:
            video_path: Path to the video file
            
        Returns:
            VideoMetadata object with color metadata
            
        Raises:
            CommandExecutionError: If there is an error executing ffprobe
        """
        metadata = VideoMetadata()
        
        try:
            properties = self.get_video_properties(video_path)
            
            metadata.color_primaries = properties["color_primaries"]
            metadata.color_transfer = properties["color_transfer"]
            metadata.color_space = properties["color_space"]
            
            return metadata
        except Exception as e:
            logger.error(f"Error reading video metadata: {e}")
            return metadata

    def get_bit_depth(self, pixel_format: str) -> int:
        """
        Get bit depth from pixel format
        
        Args:
            pixel_format: Pixel format string (e.g., "yuv420p", "yuv420p10le")
            
        Returns:
            Bit depth (8, 10, or 12)
        """
        # Default to 8-bit
        bit_depth = 8
        
        # Check for 10-bit or 12-bit formats
        if "10" in pixel_format:
            bit_depth = 10
        elif "12" in pixel_format:
            bit_depth = 12
            
        logger.debug(f"Pixel format {pixel_format} has {bit_depth}-bit depth")
        return bit_depth



    def get_video_stats(self, video_path: Union[str, pathlib.Path], nframes: int = 12) -> VideoStats:
        """
        Extract video statistics for profile detection using FFmpeg
        
        Args:
            video_path: Path to the video file
            nframes: Number of frames to analyze
            
        Returns:
            VideoStats object with video statistics
            
        Raises:
            CommandExecutionError: If there is an error executing ffmpeg
        """
        video_path = pathlib.Path(video_path)
        logger.info(f"Analyzing video color profile by sampling {nframes} frames (looking for brightness, saturation patterns)...")
        
        # Get all video properties in a single call
        properties = self.get_video_properties(video_path)
        
        # Get bit depth for scaling
        pixel_format = properties["pix_fmt"]
        bit_depth = self.get_bit_depth(pixel_format)
        max_value = (1 << bit_depth) - 1  # 255 for 8-bit, 1023 for 10-bit
        
        # Get frame rate and duration
        fps = properties.get("fps", 30.0)
        duration = properties.get("duration", 0.0)
        
        # Calculate frame interval skip factor
        if duration < 1:
            skip_factor = 1  # Don't skip frames for very short videos
        else:
            frames_total = int(fps * duration)
            skip_factor = max(1, frames_total // (nframes * 2))
            
        logger.debug(f"Video duration: {duration:.2f}s, frame rate: {fps} fps, skipping every {skip_factor} frames")
        
        # Create a temporary directory for stats
        with tempfile.TemporaryDirectory(prefix="framecut_profile_") as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir)
            stats_file = temp_dir_path / "stats.txt"
            
            # Use ffmpeg with signalstats filter
            cmd = [
                "ffmpeg", "-v", "error",
                "-i", str(video_path),
                "-vf", f"select='not(mod(n\\,{skip_factor}))',signalstats,metadata=print:file={stats_file}",
                "-frames:v", str(nframes),
                "-an",  # No audio
                "-f", "null",
                "-"
            ]
            
            try:
                run_command(cmd)
                
                # Check if stats file exists and has content
                if not stats_file.exists() or stats_file.stat().st_size == 0:
                    logger.warning(f"Stats file was not created or is empty, using default values")
                    return VideoStats(p90y=0.7*max_value, satavg=0.3*MAX_SAT, yavg=0.5*max_value)
                
                # Read stats file
                with open(stats_file, 'r') as f:
                    stats_lines = f.readlines()
                
                # Parse stats
                lavg_values = []
                satavg_values = []
                yavg_values = []
                
                for line in stats_lines:
                    if "lavfi.signalstats.YAVG=" in line:
                        parts = line.strip().split("=")
                        if len(parts) == 2:
                            yavg_values.append(float(parts[1]))
                    
                    if "lavfi.signalstats.SATAVG=" in line:
                        parts = line.strip().split("=")
                        if len(parts) == 2:
                            satavg_values.append(float(parts[1]))
                    
                    if "lavfi.signalstats.HUEAVG=" in line:
                        parts = line.strip().split("=")
                        if len(parts) == 2:
                            lavg_values.append(float(parts[1]))
                
                # Use defaults if no brightness data
                if not yavg_values:
                    logger.warning(f"No valid YAVG values found in stats, using default values")
                    return VideoStats(p90y=0.7*max_value, satavg=0.3*MAX_SAT, yavg=0.5*max_value)
                
                # Calculate statistics
                yavg_values.sort()
                p90_index = int(0.9 * len(yavg_values))
                if p90_index >= len(yavg_values):
                    p90_index = len(yavg_values) - 1
                
                p90y = yavg_values[p90_index]
                yavg = statistics.mean(yavg_values)
                
                # Saturation (if available)
                satavg = statistics.mean(satavg_values) if satavg_values else 0.3 * MAX_SAT
                
                return VideoStats(p90y=p90y, satavg=satavg, yavg=yavg)
                
            except Exception as e:
                logger.warning(f"Error analyzing video with signalstats: {e}")
                
        # If analysis with signalstats failed, use metadata-based approach
        metadata = self.get_video_metadata(video_path)
        
        # D-Log usually has characteristic brightness values
        # For 10-bit video, typically around 40-60% of max
        p90y = 0.7 * max_value
        satavg = 0.3 * MAX_SAT
        yavg = 0.5 * max_value
        
        # If 10-bit video without clear color space metadata
        # it's likely D-Log (especially for DJI Mavic 2 Pro)
        if "10" in pixel_format and not (metadata.color_transfer or metadata.color_primaries):
            # Assign values typical for D-Log
            p90y = 0.65 * max_value
            yavg = 0.45 * max_value
            satavg = 0.25 * MAX_SAT
            logger.debug("Using typical D-Log values for 10-bit video with no color metadata")
        
        logger.debug(f"Video statistics (fallback): p90y={p90y/max_value:.4f}, satavg={satavg/MAX_SAT:.4f}, yavg={yavg/max_value:.4f}")
        
        return VideoStats(p90y=p90y, satavg=satavg, yavg=yavg)

    def check_condition(self, stat_name: str, stat_value: float, condition: Dict[str, float]) -> bool:
        """
        Check if a statistic meets a condition
        
        Args:
            stat_name: Name of the statistic
            stat_value: Value of the statistic
            condition: Condition dictionary (min/max)
            
        Returns:
            True if condition is met, False otherwise
        """
        if "min" in condition and stat_value < condition["min"]:
            logger.debug(f"Condition failed: {stat_name}={stat_value:.2f} < min={condition['min']:.2f}")
            return False
            
        if "max" in condition and stat_value > condition["max"]:
            logger.debug(f"Condition failed: {stat_name}={stat_value:.2f} > max={condition['max']:.2f}")
            return False
            
        return True

    def check_all_conditions(self, conditions: List[Dict[str, Dict[str, float]]], stats: Dict[str, float]) -> bool:
        """
        Check if video stats meet all conditions in at least one rule
        
        Args:
            conditions: List of conditions to check
            stats: Dictionary of statistics to check against
            
        Returns:
            True if any rule is satisfied, False otherwise
        """
        if not conditions:
            return False
            
        for rule in conditions:
            rule_satisfied = True
            
            for stat_name, condition in rule.items():
                if stat_name not in stats:
                    rule_satisfied = False
                    break
                    
                if not self.check_condition(stat_name, stats[stat_name], condition):
                    rule_satisfied = False
                    break
                    
            if rule_satisfied:
                return True
                
        return False

    def detect_profile_from_metadata(self, metadata: VideoMetadata, device_type: Optional[str] = None) -> Optional[str]:
        """
        Detect color profile from container metadata
        
        Args:
            metadata: VideoMetadata object with color information
            device_type: Optional device type to check compatibility
            
        Returns:
            Detected color profile or None if undetermined
        """
        # First check for D-Cinelike marker in DJI's private tag
        if metadata.dji_color_mode is not None:
            if "D-CINELIKE" in metadata.dji_color_mode.upper():
                # D-Cinelike is not available for Mavic 2 Pro
                if device_type == DeviceType.MAVIC_2_PRO.value:
                    return None
                return ColorProfile.D_CINELIKE.value
            elif "NORMAL" in metadata.dji_color_mode.upper():
                return ColorProfile.NORMAL.value
                
        # Then check color space and transfer function
        return profile_manager.detect_from_metadata(metadata.color_primaries, metadata.color_transfer)

    def detect_profile(self, video_path: Union[str, pathlib.Path], device_type: str) -> str:
        """
        Detect color profile based on video statistics and device-specific detection rules
        
        Args:
            video_path: Path to the video file
            device_type: Device type string (e.g., 'DJI Mini 3 Pro')
            
        Returns:
            Detected profile key ('normal', 'd_cinelike', 'd_log', 'hlg')
            
        Raises:
            DeviceError: If device is not supported
            CommandExecutionError: If there is an error executing commands
        """
        # Get detection settings for the device
        detection_settings = device_manager.get_detection_settings(device_type)
        if not detection_settings:
            logger.warning(f"No profile detection rules for {device_type}, using normal")
            return ColorProfile.NORMAL.value
        
        # Determine video bit depth
        pixel_format = self.get_pixel_format(video_path)
        bit_depth = self.get_bit_depth(pixel_format)
        
        # Calculate max luma value based on bit depth
        max_luma = (1 << bit_depth) - 1  # 255 for 8-bit, 1023 for 10-bit
        
        # Try to detect from metadata first (fastest method)
        metadata = self.get_video_metadata(video_path)
        profile_from_metadata = self.detect_profile_from_metadata(metadata, device_type)
        
        if profile_from_metadata:
            logger.info(f"Using profile detected from metadata: {profile_from_metadata}")
            return profile_from_metadata
        
        # Select bit depth category
        bit_category = "10bit" if bit_depth >= 10 else "8bit"
        device_bit_settings = detection_settings[bit_category]
        default_profile = device_bit_settings["default"]
        
        logger.debug(f"Detected {bit_depth}-bit video for {device_type}, using {bit_category} rules")
        
        # If no profiles defined, return the default profile
        if "profiles" not in device_bit_settings or not device_bit_settings["profiles"]:
            logger.debug(f"Using default profile for {bit_category} {device_type}: {default_profile}")
            return default_profile
        
        # Analyze video to get statistics
        stats = self.get_video_stats(video_path, nframes=15)
        
        # Normalize values based on actual max values
        norm_stats = {
            "p90y": stats.p90y / max_luma,
            "satavg": stats.satavg / MAX_SAT,
            "yavg": stats.yavg / max_luma
        }
        
        # Log video statistics only once, in a shorter format
        logger.debug(f"Video stats for profile detection: " 
                    f"p90y={stats.p90y:.3f}, satavg={stats.satavg:.3f}, yavg={stats.yavg:.3f}")
        
        # Check each profile's conditions
        for profile_name, conditions in device_bit_settings["profiles"].items():
            if self.check_all_conditions(conditions, norm_stats):
                return profile_name
        
        # If no profiles matched, use the default profile
        logger.debug(f"No profile rules matched, using default: {default_profile}")
        return default_profile

    def detect_color_profile(self, video_path: Union[str, pathlib.Path], device_type: str) -> str:
        """
        Detect color profile using available methods
        
        Args:
            video_path: Path to the video file
            device_type: Device type string (e.g., 'DJI Mini 3 Pro')
            
        Returns:
            Detected profile key ('normal', 'd_cinelike', 'd_log', 'hlg')
            
        Raises:
            DeviceError: If device is not supported
        """
        try:
            # Check that device is supported
            if device_type not in device_manager.get_supported_devices():
                logger.warning(f"Unknown device type: {device_type}, using normal profile")
                return ColorProfile.NORMAL.value
                
            # Don't log here, as detection message is already shown in the calling method
            return self.detect_profile(video_path, device_type)
        except Exception as e:
            logger.error(f"Error in profile detection: {e}")
            logger.info("Falling back to default normal profile")
            return ColorProfile.NORMAL.value

    def detect_color_profile_from_all_sources(
        self, 
        video_path: Union[str, pathlib.Path], 
        device_type: Optional[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Comprehensive detection of color profile using all available methods
        
        Args:
            video_path: Path to the video file
            device_type: Device type string (e.g., 'DJI Mini 3 Pro')
            metadata: Optional metadata dictionary from exiftool
            
        Returns:
            Tuple of (detected_profile, detection_method_source)
        """
        color_profile = ColorProfile.NORMAL.value  # Default fallback
        profile_source = "default"
        
        # Step 1: Try to detect color profile from metadata text fields
        if metadata:
            # Look for profile info in video metadata
            comment = metadata.get("Comment", "").lower()
            category = metadata.get("Category", "").lower()
            description = metadata.get("Description", "").lower()
            encoder = metadata.get("Encoder", "").lower()
            
            # Check various fields that might contain color profile info
            all_text = f"{comment} {category} {description} {encoder}".lower()
            logger.debug(f"Text to search for color profile: {all_text[:200]}...")
            
            if "d-cinelike" in all_text or "d_cinelike" in all_text:
                # D-Cinelike is not available for Mavic 2 Pro
                if device_type != DeviceType.MAVIC_2_PRO.value:
                    color_profile = ColorProfile.D_CINELIKE.value
                    profile_source = "metadata"
            elif "d-log" in all_text or "d_log" in all_text:
                color_profile = ColorProfile.D_LOG.value
                profile_source = "metadata"
            elif "hlg" in all_text:
                color_profile = ColorProfile.HLG.value
                profile_source = "metadata"
        
        # Step 2: If no color profile detected from metadata, try looking for SRT file
        if profile_source == "default" and device_type:
            # Check if SRT file exists
            srt_path = pathlib.Path(video_path).with_suffix('.SRT')
            if not srt_path.exists():
                srt_path = pathlib.Path(video_path).with_suffix('.srt')
            
            if srt_path.exists():
                logger.info(f"Found SRT file: {srt_path}")
                # Try to find color profile in SRT
                try:
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        srt_content = f.read().lower()
                        
                    # Check for color profile in SRT content
                    if "[color_md : d_cinelike]" in srt_content or "d-cinelike" in srt_content:
                        color_profile = ColorProfile.D_CINELIKE.value
                        profile_source = "SRT"
                    elif "[color_md : d_log]" in srt_content or "d-log" in srt_content:
                        color_profile = ColorProfile.D_LOG.value
                        profile_source = "SRT"
                    elif "[color_md : hlg]" in srt_content or "hlg" in srt_content:
                        color_profile = ColorProfile.HLG.value
                        profile_source = "SRT"
                except Exception as e:
                    logger.error(f"Error reading SRT file: {e}")
            else:
                logger.debug("No SRT file found")
        
        # Step 3: If still using default and we know the device type, use our enhanced detection
        if profile_source == "default" and device_type:
            try:
                # Use our advanced detection based on video content analysis
                logger.debug(f"Calling advanced profile detection for {device_type}")
                detected_profile = self.detect_color_profile(video_path, device_type)
                if detected_profile:
                    color_profile = detected_profile
                    profile_source = "content analysis"
            except Exception as e:
                logger.error(f"Error in advanced profile detection: {e}")
                # Continue with default or previously detected profile
        
        # Log the detected color profile with its source
        if profile_source != "default":
            logger.debug(f"Detected color profile: {profile_manager.get_profile_display_name(color_profile)} (source: {profile_source})")
        else:
            logger.debug(f"Using color profile: {profile_manager.get_profile_display_name(color_profile)}")
        
        return color_profile, profile_source

    def detect_device_type(self, video_path: Union[str, pathlib.Path]) -> Optional[str]:
        """
        Detect only the device type from video metadata without analyzing color profile
        
        Args:
            video_path: Path to video file
            
        Returns:
            Detected device type or None if undetermined
            
        Raises:
            CommandExecutionError: If there is an error executing exiftool
        """
        try:
            video_path = pathlib.Path(video_path)
            
            # Get video metadata using exiftool
            cmd = ["exiftool", "-j", video_path]
            result = run_command(cmd)
            metadata = json.loads(result.stdout)
            
            if not metadata:
                logger.warning("No metadata found in video file")
                return None
                
            metadata = metadata[0]  # exiftool returns a list with one element
            
            # Log some of the key metadata fields for debugging
            logger.debug(f"File: {metadata.get('FileName', 'Unknown')}")
            logger.debug(f"Make: {metadata.get('Make', 'Unknown')}")
            logger.debug(f"Model: {metadata.get('Model', 'Unknown')}")
            logger.debug(f"Encoder: {metadata.get('Encoder', 'Unknown')}")
            logger.debug(f"Created: {metadata.get('CreateDate', 'Unknown')}")
            
            # Check for device information in various metadata fields
            make = metadata.get("Make", "")
            model = metadata.get("Model", "")
            encoder = metadata.get("Encoder", "")
            
            # Detect device type
            device_type = None
            if "DJI Mini 3 Pro" in model or "Mini 3 Pro" in encoder:
                device_type = DeviceType.MINI_3_PRO.value
            elif "Mavic 2 Pro" in model or "Mavic 2 Pro" in encoder:
                device_type = DeviceType.MAVIC_2_PRO.value
            elif "OsmoAction5 Pro" in encoder or "Osmo Action 5 Pro" in encoder or "Action 5" in model:
                device_type = DeviceType.ACTION_5_PRO.value
                
            if device_type:
                logger.debug(f"Detected device: {device_type}")
                return device_type
            else:
                # Improve warning message by replacing empty values with "N/A"
                make_str = make if make else "N/A"
                model_str = model if model else "N/A"
                encoder_str = encoder if encoder else "N/A"
                logger.warning(f"Unknown device type. Make: {make_str}, Model: {model_str}, Encoder: {encoder_str}")
                return None
                
        except Exception as e:
            logger.error(f"Error detecting device: {e}", exc_info=True)
            return None


# Create a singleton instance for global use
video_analyzer = VideoAnalyzer() 
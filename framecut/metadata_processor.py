# -*- coding: utf-8 -*-
"""
Metadata handling module for Framecut

Functions for extracting and manipulating metadata from video files and SRT files.
"""

import re
import json
import decimal
from datetime import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Dict

from framecut.utils import logger, parse_timestamp, run_command
from framecut.exceptions import MetadataError
from framecut.device_settings import device_manager


class MetadataProcessor:
    """Handles metadata extraction and processing from videos and SRT files"""
    
    def find_srt_telemetry(self, srt_path: Union[str, Path], target_timestamp: str) -> Optional[Dict[str, Any]]:
        """
        Find the closest telemetry data in the SRT file to the given timestamp
        Based on the algorithm from srt2tiff.py
        
        Args:
            srt_path: Path to SRT file
            target_timestamp: Target timestamp to find telemetry for
            
        Returns:
            Dictionary with telemetry data or None if not found
            
        Raises:
            MetadataError: If there is an error processing the SRT file
        """
        window = 0.20  # Default tolerance in seconds
        target_seconds = parse_timestamp(target_timestamp)
        srt_path = Path(srt_path)
        
        logger.debug(f"Searching for telemetry in {srt_path} near {target_timestamp}")
        
        # Telemetry regex pattern
        tele_re = re.compile(
            r"\[iso\s*:\s*(?P<iso>\d+)].*?"
            r"\[shutter\s*:\s*(?P<shut>[^]]+)].*?"
            r"\[fnum\s*:\s*(?P<fnum>\d+)].*?"
            r"\[ev\s*:\s*(?P<ev>-?\d+\.\d+|\-?\d+)].*?"
            r"(?:\[ct\s*:\s*\d+].*?)?"  # Optional ct field
            r"(?:\[color_md\s*:\s*[^]]+].*?)?"  # Optional color_md field
            r"\[focal_len\s*:\s*(?P<flen>\d+)].*?"
            r"(?:\[dzoom_ratio\s*:\s*\d+,\s*delta\s*:\s*\d+].*?)?"  # Optional dzoom_ratio field
            r"\[(?:latitude|lat)\s*:\s*(?P<lat>-?\d+\.\d+)].*?"
            r"\[(?:longitude|long)\s*:\s*(?P<lon>-?\d+\.\d+)].*?"
            r"(?:abs_alt|altitude)\s*:\s*(?P<abs_alt>-?\d+\.\d+)",  # Only capture absolute altitude
            re.IGNORECASE
        )
        time_re = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        
        # Search for the closest matching telemetry
        best = None  # (diff, tele_line, date_line)
        
        try:
            if not srt_path.exists():
                logger.warning(f"SRT file not found: {srt_path}")
                return None
                
            lines = srt_path.read_text(encoding='utf-8').splitlines()
            logger.debug(f"Read {len(lines)} lines from SRT file")
            
            i = 0
            while i < len(lines):
                # Find timestamp lines
                if ' --> ' not in lines[i]:
                    i += 1
                    continue
                    
                # Parse SRT timestamp
                hh, mm, sms = lines[i].split()[0].split(':')
                ss, ms = sms.replace(',', '.').split('.')
                t = int(hh)*3600 + int(mm)*60 + int(ss) + int(ms)/1000
                diff = abs(t - target_seconds)
                
                # Look for telemetry in next few lines
                date_line = None
                tele_line = None
                for j in range(1, 6):
                    if i+j >= len(lines): 
                        break
                    txt = lines[i+j].strip()
                    if time_re.match(txt): 
                        date_line = txt.split('.')[0]
                    if '[iso' in txt.lower():
                        tele_line = txt
                        break
                        
                if tele_line and (best is None or diff < best[0]):
                    best = (diff, tele_line, date_line)
                i += 1
                
            if best is None or best[0] > window:
                logger.warning(f"No telemetry found within ±{window:.2f}s of {target_timestamp}")
                return None
                
            # Parse telemetry data
            diff, tele_line, date_line = best
            if not date_line:
                date_line = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                logger.warning("No date found in telemetry, using current time")
                
            m = tele_re.search(tele_line)
            if not m:
                logger.error(f"Telemetry line not recognized: '{tele_line}'")
                return None
                
            # Parse matched groups
            g = m.groupdict()
            
            # Handle altitude - prefer abs_alt over anything else
            altitude = None
            if 'abs_alt' in g and g['abs_alt']:
                altitude = g['abs_alt']
                
            # Format data
            telemetry = {
                'iso': g['iso'],
                'shutter': g['shut'].split('.')[0],  # '1/500.0' → '1/500'
                'fnumber': decimal.Decimal(g['fnum']) / 100,  # 170 → 1.7
                'ev': g['ev'],
                'focal_length': decimal.Decimal(g['flen']) / 10,  # 240 → 24.0 mm
                'latitude': g['lat'],
                'latitude_ref': 'N' if decimal.Decimal(g['lat']) >= 0 else 'S',
                'longitude': g['lon'],
                'longitude_ref': 'E' if decimal.Decimal(g['lon']) >= 0 else 'W',
                'altitude': altitude,
                'altitude_ref': '0' if altitude and decimal.Decimal(altitude) >= 0 else '1',
                'datetime': date_line,
            }
            
            # Format date string for EXIF
            try:
                dt_obj = datetime.strptime(date_line, '%Y-%m-%d %H:%M:%S')
                telemetry['date_str'] = dt_obj.strftime('%Y:%m:%d %H:%M:%S')
            except:
                telemetry['date_str'] = datetime.utcnow().strftime('%Y:%m:%d %H:%M:%S')
            
            logger.debug(f"Found telemetry at {telemetry['date_str']} (time diff: {diff*1000:.0f}ms)")
            logger.debug(f"Telemetry data: ISO={telemetry['iso']}, "
                       f"Shutter={telemetry['shutter']}, "
                       f"FNumber={telemetry['fnumber']}, "
                       f"GPS: {telemetry['latitude']} {telemetry['latitude_ref']}, "
                       f"{telemetry['longitude']} {telemetry['longitude_ref']}")
            return telemetry
        except Exception as e:
            logger.error(f"Error parsing SRT file: {e}", exc_info=True)
            raise MetadataError(f"Error parsing SRT file: {str(e)}") from e

    def extract_metadata_from_video(self, video_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Extract metadata directly from video file using exiftool
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with metadata or None if not found
            
        Raises:
            MetadataError: If there is an error extracting metadata
        """
        try:
            video_path = Path(video_path)
            logger.debug("Extracting metadata directly from video file...")
            cmd = ["exiftool", "-j", video_path]
            result = run_command(cmd)
            metadata = json.loads(result.stdout)
            
            if not metadata:
                logger.warning("No metadata found in video file")
                return None
                
            metadata = metadata[0]  # exiftool returns a list with one element
            
            # Extract relevant fields
            telemetry = {
                'iso': metadata.get('ISO', '100'),
                'shutter': metadata.get('ExposureTime', '1/60'),
                'fnumber': metadata.get('FNumber', 2.8),
                'ev': metadata.get('ExposureCompensation', '0'),
                'focal_length': metadata.get('FocalLength', '24.0'),
                'date_str': metadata.get('CreateDate', datetime.utcnow().strftime('%Y:%m:%d %H:%M:%S')).replace('-', ':'),
            }
            
            # Log extracted metadata
            logger.debug(f"Extracted metadata: ISO={telemetry['iso']}, "
                       f"Shutter={telemetry['shutter']}, "
                       f"FNumber={telemetry['fnumber']}")
            
            # GPS data if available
            if 'GPSLatitude' in metadata:
                telemetry['latitude'] = metadata.get('GPSLatitude', '0')
                telemetry['latitude_ref'] = metadata.get('GPSLatitudeRef', 'N')
                telemetry['longitude'] = metadata.get('GPSLongitude', '0')
                telemetry['longitude_ref'] = metadata.get('GPSLongitudeRef', 'E')
                telemetry['altitude'] = metadata.get('GPSAltitude', '0')
                telemetry['altitude_ref'] = metadata.get('GPSAltitudeRef', '0')
                logger.debug(f"GPS data found: {telemetry['latitude']} {telemetry['latitude_ref']}, "
                            f"{telemetry['longitude']} {telemetry['longitude_ref']}")
            else:
                logger.warning("No GPS data found in video metadata")
            
            logger.debug(f"Successfully extracted metadata from video file")
            return telemetry
        except Exception as e:
            logger.error(f"Error extracting metadata from video: {e}", exc_info=True)
            raise MetadataError(f"Error extracting metadata from video: {str(e)}") from e

    def get_device_info(self, device: str) -> Dict[str, str]:
        """
        Get device make and model based on device identifier
        
        Args:
            device: Device identifier (e.g., 'dji mavic air 2', 'gopro hero 9')
            
        Returns:
            Dictionary with 'make' and 'model' keys
        """
        device_lower = device.lower()
        
        # Try to find device in supported devices
        found_device = device_manager.find_device_by_name(device_lower)
        if found_device:
            return device_manager.get_device_make_model(found_device)
            
        # No match found, try to extract make and model
        parts = device.split(' ', 1)
        make = parts[0]
        
        # For model, remove the manufacturer name if it's at the beginning
        if len(parts) > 1:
            model = parts[1]
        else:
            model = device
            
        # Ensure model doesn't start with make (to prevent duplication)
        if model.lower().startswith(make.lower() + " "):
            model = model[len(make)+1:]
        elif model.lower() == make.lower():
            model = model  # If only one word provided, use it for both
            
        return {
            "make": make,
            "model": model
        }

    def write_exif_metadata(
            self, 
            tiff_path: Union[str, Path], 
            telemetry: Dict[str, Any], 
            device: Optional[str] = None
        ) -> bool:
            """
            Write EXIF metadata to a TIFF file
            
            Args:
                tiff_path: Path to TIFF file
                telemetry: Dictionary with metadata values
                device: Optional device identifier (e.g., 'DJI Mavic Air 2', 'GoPro Hero 9')
                
            Returns:
                True if successful, False otherwise
                
            Raises:
                MetadataError: If there is an error writing metadata
            """
            try:
                tiff_path = Path(tiff_path)
                
                logger.debug(f"Writing EXIF metadata to {tiff_path}...")
                
                # Prepare exiftool arguments
                exiftool_args = []
                
                # Basic camera settings
                if "iso" in telemetry:
                    exiftool_args.extend(["-ISO=" + str(telemetry["iso"])])
                
                if "shutter" in telemetry:
                    exiftool_args.extend(["-ExposureTime=" + str(telemetry["shutter"])])
                
                if "fnumber" in telemetry:
                    exiftool_args.extend(["-FNumber=" + str(telemetry["fnumber"])])
                
                if "ev" in telemetry:
                    exiftool_args.extend(["-ExposureCompensation=" + str(telemetry["ev"])])
                
                if "focal_length" in telemetry:
                    exiftool_args.extend(["-FocalLength=" + str(telemetry["focal_length"])])
                
                # GPS data if available
                if "latitude" in telemetry and "longitude" in telemetry:
                    exiftool_args.extend([
                        "-GPSLatitude=" + str(telemetry["latitude"]),
                        "-GPSLatitudeRef=" + str(telemetry.get("latitude_ref", "North")),
                        "-GPSLongitude=" + str(telemetry["longitude"]),
                        "-GPSLongitudeRef=" + str(telemetry.get("longitude_ref", "West")),
                    ])
                    
                    if "altitude" in telemetry:
                        exiftool_args.extend([
                            "-GPSAltitude=" + str(telemetry["altitude"]) + " m Above Sea Level",
                            "-GPSAltitudeRef=" + ("Above Sea Level" if telemetry.get("altitude_ref") == "0" else "Below Sea Level"),
                        ])
                
                # Date information
                if "date_str" in telemetry:
                    date_str = telemetry["date_str"]
                    # Use same date for both original capture and creation
                    exiftool_args.extend([
                        "-DateTimeOriginal=" + date_str,
                        "-CreateDate=" + date_str,
                    ])
                
                # Color space - set sRGB for compatibility
                exiftool_args.extend(["-ColorSpace=sRGB"])
                
                # Device make/model
                if device:
                    device_info = self.get_device_info(device)
                    make = device_info.get("make", "Unknown")
                    model = device_info.get("model", device)
                    
                    exiftool_args.extend([
                        "-Make=" + make,
                        "-Model=" + model,
                    ])
                
                # Run exiftool to write metadata
                cmd = ["exiftool"] + exiftool_args + ["-overwrite_original", tiff_path]
                run_command(cmd)
                
                # Sync file timestamp with DateTimeOriginal
                logger.debug("Syncing file timestamp with DateTimeOriginal")
                cmd = ["exiftool", "-DateTimeOriginal>FileModifyDate", "-m", "-overwrite_original", tiff_path]
                run_command(cmd)
                
                # Add success message for metadata writing
                logger.info(f"✓ Metadata written to {tiff_path}")
                
                return True
            except Exception as e:
                logger.error(f"Error writing metadata: {e}")
                raise MetadataError(f"Error writing metadata: {str(e)}") from e

    def find_matching_srt(self, video_path: Union[str, Path]) -> Optional[Path]:
        """
        Look for an SRT file with the same name as the video
        
        Args:
            video_path: Path to video file
            
        Returns:
            Path to SRT file or None if not found
        """
        video_path = Path(video_path)
        
        # Try both uppercase and lowercase extensions
        for ext in ['.SRT', '.srt']:
            srt_path = video_path.with_suffix(ext)
            if srt_path.exists():
                logger.debug(f"Found SRT file for metadata transfer: {srt_path}")
                return srt_path
            
        logger.debug(f"SRT file not found for: {video_path}")
        return None


# Create a singleton instance for global use
metadata_processor = MetadataProcessor() 
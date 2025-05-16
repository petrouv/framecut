# -*- coding: utf-8 -*-
"""
Device settings module for Framecut

Contains optimized settings for specific DJI devices and their supported color profiles.
"""

from typing import Dict, List, Optional, Any, Set, Union

from framecut.enums import DeviceType, ColorProfile
from framecut.exceptions import DeviceError, ProfileError
from framecut.color_profiles import profile_manager

# Unified device data structure
# Contains information about supported profiles and detection rules
DEVICES: Dict[str, Dict[str, Any]] = {
    DeviceType.MINI_3_PRO.value: {
        # Device information
        "make": "DJI",
        "model": "Mini 3 Pro",
        
        # Supported profiles
        "profiles": {
            ColorProfile.NORMAL.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.NORMAL.value)
            },
            ColorProfile.D_CINELIKE.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.D_CINELIKE.value)
            }
        },
        
        # Detection settings for profile
        "detection": {
            "8bit": {
                "default": ColorProfile.NORMAL.value,
                "profiles": {
                    ColorProfile.D_CINELIKE.value: profile_manager.get_detection_conditions(ColorProfile.D_CINELIKE.value)
                }
            },
            "10bit": {
                "default": ColorProfile.D_CINELIKE.value,  # 10-bit on Mini 3 Pro is always D-Cinelike
                "profiles": {}
            }
        }
    },
    
    DeviceType.MAVIC_2_PRO.value: {
        # Device information
        "make": "DJI",
        "model": "Mavic 2 Pro",
        
        "profiles": {
            ColorProfile.NORMAL.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.NORMAL.value)
            },
            ColorProfile.D_LOG.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.D_LOG.value)
            },
            ColorProfile.HLG.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.HLG.value)
            }
        },
        "detection": {
            "8bit": {
                "default": ColorProfile.NORMAL.value,
                "profiles": {}
            },
            "10bit": {
                "default": ColorProfile.D_LOG.value,
                "profiles": {
                    ColorProfile.HLG.value: profile_manager.get_detection_conditions(ColorProfile.HLG.value),
                    ColorProfile.D_LOG.value: profile_manager.get_detection_conditions(ColorProfile.D_LOG.value)
                }
            }
        }
    },
    
    DeviceType.ACTION_5_PRO.value: {
        # Device information
        "make": "DJI",
        "model": "Osmo Action 5 Pro",
        
        "profiles": {
            ColorProfile.NORMAL.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.NORMAL.value)
            },
            ColorProfile.D_LOG.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.D_LOG.value)
            },
            ColorProfile.HLG.value: {
                "ffmpeg_params": profile_manager.get_ffmpeg_params(ColorProfile.HLG.value)
            }
        },
        "detection": {
            "8bit": {
                "default": ColorProfile.NORMAL.value,
                "profiles": {}
            },
            "10bit": {
                "default": ColorProfile.NORMAL.value,
                "profiles": {
                    # Specialized conditions for Action 5 Pro
                    ColorProfile.HLG.value: [
                        {"p90y": {"min": 0.85}, "satavg": {"min": 0.45}}  # High brightness and saturation
                    ],
                    ColorProfile.D_LOG.value: [
                        # Main rule for D-Log with expanded range
                        {"p90y": {"min": 0.45, "max": 0.80}, "satavg": {"min": 0.25, "max": 0.45}, "yavg": {"max": 0.50}},
                        # Additional rule for underexposed footage
                        {"p90y": {"min": 0.40, "max": 0.82}, "yavg": {"min": 0.30, "max": 0.50}, "satavg": {"min": 0.20}}
                    ]
                }
            }
        }
    }
}


class DeviceManager:
    """Manages device settings and profiles"""
    
    def __init__(self) -> None:
        self.devices = DEVICES
        
    def get_supported_devices(self) -> List[str]:
        """
        Returns a list of supported device names
        
        Returns:
            List of device names
        """
        return list(self.devices.keys())
    
    def validate_device(self, device: str) -> None:
        """
        Validates that a device is supported
        
        Args:
            device: Device name to validate
            
        Raises:
            DeviceError: If device is not supported
        """
        if device not in self.get_supported_devices():
            available_devices = ", ".join(self.get_supported_devices())
            raise DeviceError(f"Unsupported device: {device}. Available devices: {available_devices}")
    
    def get_supported_profiles(self, device: str) -> List[str]:
        """
        Get supported color profiles for a device
        
        Args:
            device: Device name (e.g., "DJI Mini 3 Pro")
            
        Returns:
            List of supported profile names
            
        Raises:
            DeviceError: If device is not supported
        """
        if device not in self.devices:
            raise DeviceError(f"Unsupported device: {device}")
            
        return list(self.devices[device]["profiles"].keys())
    
    def get_detection_settings(self, device: str) -> Dict[str, Any]:
        """
        Get profile detection rules for a specific device
        
        Args:
            device: Device type (e.g., "DJI Mini 3 Pro")
            
        Returns:
            Dictionary with detection settings
            
        Raises:
            DeviceError: If device is not supported
        """
        if device not in self.devices:
            raise DeviceError(f"Unsupported device: {device}")
            
        return self.devices[device]["detection"]
    
    def get_device_ffmpeg_params(self, device: str, profile: str) -> List[str]:
        """
        Get FFmpeg parameters for a specific device and profile
        
        Args:
            device: Device type (e.g., "DJI Mini 3 Pro")
            profile: Color profile (e.g., "normal", "d_cinelike")
            
        Returns:
            List of FFmpeg parameters for the given device and profile
            
        Raises:
            DeviceError: If device is not supported
            ProfileError: If profile is not supported for the device
        """
        # Make sure device is valid
        self.validate_device(device)
        
        # Make sure profile is valid for device
        if profile not in self.get_supported_profiles(device):
            supported_profiles = ", ".join(self.get_supported_profiles(device))
            raise ProfileError(
                f"Profile '{profile}' is not supported for device {device}. "
                f"Supported profiles: {supported_profiles}"
            )
            
        # Get profile specific parameters
        return self.devices[device]["profiles"][profile]["ffmpeg_params"]
    
    def get_device_make_model(self, device_type: str) -> Dict[str, str]:
        """
        Get make and model for a device type
        
        Args:
            device_type: Device type (e.g., "DJI Mini 3 Pro")
            
        Returns:
            Dictionary with make and model keys
            
        Raises:
            DeviceError: If device is not supported
        """
        if device_type not in self.devices:
            # Default values if not found
            return {"make": "Unknown", "model": device_type}
            
        device_info = self.devices[device_type]
        return {
            "make": device_info.get("make", "Unknown"),
            "model": device_info.get("model", device_type)
        }
    
    def find_device_by_name(self, name: str) -> Optional[str]:
        """
        Find a supported device by partial name matching
        
        Args:
            name: Device name to search for (e.g., 'mavic 2 pro', 'mini 3')
            
        Returns:
            Device identifier if found, None otherwise
        """
        name_lower = name.lower()
        
        # First try exact match with device identifiers
        if name_lower in self.devices:
            return name_lower
            
        # Then try matching by model name
        for device_id, device_info in self.devices.items():
            device_model = device_info.get("model", "").lower()
            if device_model in name_lower or name_lower in device_model:
                return device_id
                
        return None


# Create a singleton instance for global use
device_manager = DeviceManager() 
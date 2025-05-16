# -*- coding: utf-8 -*-
"""
Color profile settings for Framecut

Contains FFmpeg parameters and detection rules for different color profiles.
"""

from typing import Dict, List, Optional, Any, Tuple, Set

from framecut.enums import ColorProfile
from framecut.exceptions import ProfileError

# =============================================================================
#  FFmpeg presets for extracting a **single, loss-less TIFF** frame 
#  from DJI H.265/4-2-0 footage.
#
#  ─ General assumptions ─
#  • We always work in 10-bit (or 8-bit, if that is all the camera offers) and
#    up-sample chroma to full 4 : 4 : 4 RGB with a high-quality Lanczos kernel.
#  • The common, "safe" baseline uses BT.709 tags, which are correct for all
#    SDR / D-Cinelike clips.
#  • Profiles that record in a *wide-gamut* log or HDR space override only the
#    colour metadata that actually changes (primaries / matrix / transfer‐curve);
#    everything else stays identical.
# =============================================================================

# Base FFmpeg parameters (identical for all devices)
BASE_FFMPEG_PARAMS: List[str] = [
    "-sws_flags",      "lanczos+full_chroma_int+accurate_rnd",
    "-c:v",            "tiff",
    "-pix_fmt",        "rgb48le",
    "-color_range",    "pc",
    "-color_primaries","bt709",      # default for Normal / D-Cinelike
    "-color_trc",      "bt709",
    "-colorspace",     "bt709"
]

# FFmpeg parameters for each profile
PROFILE_PARAMS: Dict[str, List[str]] = {
    ColorProfile.NORMAL.value: [],      # Use default parameters
    ColorProfile.D_CINELIKE.value: [],  # BT.709 tags are already correct
    ColorProfile.D_LOG.value: [         # D-Log M wide-gamut
        "-color_primaries", "bt2020",
        "-colorspace",      "bt2020nc",   # non-constant-luminance YUV
        "-color_trc",       "log"         # FFmpeg's generic logarithmic curve
    ],
    ColorProfile.HLG.value: [           # Hybrid-Log-Gamma HDR
        "-color_primaries", "bt2020",
        "-colorspace",      "bt2020nc",
        "-color_trc",       "arib-std-b67"
    ]
}

# Common conditions for detecting profiles based on video characteristics
BASE_DETECTION_CONDITIONS: Dict[str, List[Dict[str, Dict[str, float]]]] = {
    ColorProfile.D_CINELIKE.value: [
        {"satavg": {"max": 0.25}}  # Low saturation (< 25%)
    ],
    ColorProfile.D_LOG.value: [
        {"p90y": {"max": 0.80}, "satavg": {"max": 0.30}}  # Medium brightness and low saturation
    ],
    ColorProfile.HLG.value: [
        {"p90y": {"min": 0.88}}  # High brightness
    ]
}

# Mapping from metadata color space and transfer to color profiles
METADATA_PROFILE_MAPPING: Dict[Tuple[str, str], Optional[str]] = {
    # HLG (BT.2020 + arib-std-b67)
    ("bt2020", "arib-std-b67"): ColorProfile.HLG.value,
    
    # D-Log M (BT.2020 + log)
    ("bt2020", "log"): ColorProfile.D_LOG.value,
    
    # Normal/D-Cinelike (BT.709 + bt709)
    ("bt709", "bt709"): None  # Requires additional frame analysis
}


class ProfileManager:
    """Manages color profiles and their FFmpeg parameters"""
    
    def __init__(self) -> None:
        self.profiles = ColorProfile
    
    def get_all_profiles(self) -> List[str]:
        """
        Get list of all supported profile names
        
        Returns:
            List of profile names
        """
        return ColorProfile.get_all_profiles()
    
    def get_profile_display_name(self, profile: str) -> str:
        """
        Get human-readable name for a profile
        
        Args:
            profile: Profile identifier
            
        Returns:
            Human-readable profile name
        """
        return ColorProfile.get_display_name(profile)
    
    def validate_profile(self, profile: str) -> None:
        """
        Validate that a profile name is supported
        
        Args:
            profile: Profile name to validate
            
        Raises:
            ProfileError: If profile is not supported
        """
        if profile not in self.get_all_profiles():
            raise ProfileError(f"Unsupported color profile: {profile}")
            
    def get_ffmpeg_params(self, profile: str) -> List[str]:
        """
        Get FFmpeg parameters for a specific profile
        
        Args:
            profile: Profile name
            
        Returns:
            List of FFmpeg parameters
            
        Raises:
            ProfileError: If profile is not supported
        """
        self.validate_profile(profile)
        
        params = BASE_FFMPEG_PARAMS.copy()
        
        if profile in PROFILE_PARAMS:
            params.extend(PROFILE_PARAMS[profile])
            
        return params
    
    def get_detection_conditions(self, profile: str) -> List[Dict[str, Dict[str, float]]]:
        """
        Get detection conditions for a specific profile
        
        Args:
            profile: Profile name
            
        Returns:
            List of detection condition dictionaries
            
        Raises:
            ProfileError: If profile is not supported
        """
        self.validate_profile(profile)
        
        if profile in BASE_DETECTION_CONDITIONS:
            return BASE_DETECTION_CONDITIONS[profile]
        return []
        
    def detect_from_metadata(self, color_primaries: Optional[str], color_transfer: Optional[str]) -> Optional[str]:
        """
        Detect color profile from video container metadata
        
        Args:
            color_primaries: Color primaries from video metadata
            color_transfer: Color transfer from video metadata
            
        Returns:
            Detected profile name or None if undetermined
        """
        if not color_primaries or not color_transfer:
            return None
            
        # Normalize values to lowercase for consistency
        primaries = color_primaries.lower()
        transfer = color_transfer.lower()
        
        # Look up the combination in our mapping
        return METADATA_PROFILE_MAPPING.get((primaries, transfer))


# Create a singleton instance for global use
profile_manager = ProfileManager() 
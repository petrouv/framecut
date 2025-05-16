# -*- coding: utf-8 -*-
"""
Enumerations for Framecut

Define constants used throughout the application.
"""

from enum import Enum, auto

class DeviceType(str, Enum):
    """Device types supported by Framecut"""
    MINI_3_PRO = "DJI Mini 3 Pro"
    MAVIC_2_PRO = "DJI Mavic 2 Pro"
    ACTION_5_PRO = "DJI Osmo Action 5 Pro"


class ColorProfile(str, Enum):
    """Color profiles supported by Framecut"""
    NORMAL = "normal"
    D_CINELIKE = "d_cinelike"
    D_LOG = "d_log"
    HLG = "hlg"
    
    @classmethod
    def get_all_profiles(cls) -> list[str]:
        """Get all available color profiles"""
        return [e.value for e in cls]
    
    @classmethod
    def get_display_name(cls, profile: str) -> str:
        """Get display name for a profile ID"""
        display_names = {
            cls.NORMAL.value: "Normal",
            cls.D_CINELIKE.value: "D-Cinelike",
            cls.D_LOG.value: "D-Log",
            cls.HLG.value: "HLG"
        }
        return display_names.get(profile, profile) 
# Framecut

Framecut is a high-quality video frame extraction tool that works with any video source. It extracts frames from videos at specified timestamps while preserving maximum image quality and metadata, with special optimizations for certain DJI devices.

## Features

- Extracts high-quality frames from video files at specific timestamps
- Outputs 16-bit TIFF files optimized for post-processing in Adobe Photoshop and Lightroom
- Preserves metadata (EXIF/IPTC) from SRT telemetry files or video metadata
- Enhanced support for several DJI devices with auto-detection:
  - DJI Mini 3 Pro
  - DJI Mavic 2 Pro
  - DJI Osmo Action 5 Pro
- Bracketing mode to extract multiple frames around a timestamp
- Intelligent color profile detection and application
- Detailed logging with customizable verbosity levels

## Requirements

- Python 3.6+
- ffmpeg (for frame extraction)
- exiftool (for metadata handling)

## Installation

### From Repository

1. Clone the repository:
   ```
   git clone https://github.com/petrouv/framecut.git
   cd framecut
   ```

2. Install the package:
   ```
   pip install .
   ```

### System Dependencies

#### macOS (Homebrew)
```
brew install ffmpeg exiftool
```

#### Ubuntu/Debian
```
sudo apt-get install ffmpeg libimage-exiftool-perl
```

#### Windows
- Download and install [ffmpeg](https://ffmpeg.org/download.html)
- Download and install [exiftool](https://exiftool.org/)
- Add both to your system PATH

## Usage

### Command Line Interface

Framecut can be run in several ways:

1. Using the installed command:
   ```
   framecut video_file.MOV 00:00:10.500
   ```

2. Using the entry point script:
   ```
   python framecut.py video_file.MOV 00:00:10.500
   ```

3. Using the Python module:
   ```
   python -m framecut video_file.MOV 00:00:10.500
   ```

### Basic Examples

#### Extract a Single Frame
```
framecut video_file.MOV 00:00:10.500
```

#### Specify Output Directory
```
framecut video_file.MOV 00:00:10.500 --output /path/to/output
```

#### Enable Verbose Logging
```
framecut video_file.MOV 00:00:10.500 --verbose
```

### Advanced Usage

#### Bracketing Mode
Extract multiple frames around the specified timestamp:

```
framecut video_file.MOV 00:00:10.500 --bracketing
```

By default, this extracts 3 frames: one 0.25s before, one at the exact timestamp, and one 0.25s after.

Customize the number of frames and interval:
```
framecut video_file.MOV 00:00:10.500 --bracketing --bracket-frames 5 --bracket-interval 0.1
```

> **Note**: When using bracketing with timestamps near the start of the video, frames with negative timestamps will be automatically skipped.

#### Manual Device and Profile Specification
Override auto-detection or specify device type for optimal processing:

```
framecut video_file.MOV 00:00:10.500 --device "DJI Mini 3 Pro" --color-profile d_cinelike
```

Short form:
```
framecut video_file.MOV 00:00:10.500 -d "DJI Mini 3 Pro" -p d_cinelike
```

## Supported Devices and Color Profiles

Framecut works with any video source but has enhanced support and optimized settings for the following DJI devices:

| Device | Supported Color Profiles |
|--------|--------------------------|
| DJI Mini 3 Pro | `normal`, `d_cinelike` |
| DJI Mavic 2 Pro | `normal`, `d_log`, `hlg` |
| DJI Osmo Action 5 Pro | `normal`, `d_log`, `hlg` |

### Color Profile Details

| Profile | Description | Color Space |
|---------|-------------|-------------|
| `normal` | Standard color profile (ready-to-use SDR) | BT.709 |
| `d_cinelike` | D-Cinelike (flat SDR for grading) | BT.709 |
| `d_log` | D-Log M (10-bit, wide gamut) | BT.2020 |
| `hlg` | HLG (HDR-10) | BT.2020 |

## Metadata Handling

Framecut automatically processes metadata to enhance your workflow:

1. **SRT Telemetry**: The program looks for an SRT file with the same name as the video in the same directory. If found, it extracts GPS coordinates, altitude, and other telemetry data.

2. **Video Metadata**: If no SRT file is available, Framecut attempts to extract metadata directly from the video file.

3. **Embedding**: All extracted metadata is embedded in the output TIFF files, making it available in photo editing software.

## Technical Details

### Unified Configuration System

Framecut uses a streamlined configuration system:

- Device settings are unified in `device_settings.py`
- Base FFMPEG parameters are applied to all devices
- Device-specific parameters are applied based on detection
- Color profile settings are organized by profile type

This design makes it easy to:
- Add support for new video devices and sources
- Modify existing device-specific optimizations
- Maintain consistent output quality across all video sources

### Frame Extraction Process

1. Analysis of the video file to detect device type and color profile
2. Application of optimal ffmpeg parameters for the specific device/profile
3. Precise timestamp-based frame extraction
4. Post-processing to ensure color accuracy
5. Metadata embedding from SRT or video source

### Output Format

Frames are saved as 16-bit TIFF files with:
- Maximum quality preservation
- Proper color profile tagging
- Embedded metadata
- Naming based on source file and timestamp

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg is installed and in your PATH
2. **exiftool not found**: Ensure exiftool is installed and in your PATH
3. **Device not detected**: Use the `--device` flag to manually specify a device type for optimal processing
4. **Profile not detected**: Use the `--color-profile` flag to manually specify the profile

### Logging

Use the `--verbose` flag for detailed debug information when troubleshooting.
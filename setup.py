#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup script for Framecut package
"""

from setuptools import setup, find_packages

setup(
    name="framecut",
    version="0.1.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'framecut=framecut.main:main',
        ],
    },
    description="High-quality video frame extraction tool with optimizations for DJI devices",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="petrouv",    
    url="https://github.com/petrouv/framecut",
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Video",
    ],
    python_requires=">=3.6",
    install_requires=[
        # Requires system tools: ffmpeg, exiftool
    ],
) 
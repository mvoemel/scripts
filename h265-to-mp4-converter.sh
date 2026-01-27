#!/bin/bash
for file in *.h265; do
    ffmpeg -i "$file" -c copy "${file%.h265}.mp4"
done
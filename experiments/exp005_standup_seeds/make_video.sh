#!/usr/bin/env bash
# 使い方: bash make_video.sh <checkpoint.pt> [steps] [out.mp4] [record_video.py の追加引数...]
exec bash "$(dirname "$0")/../common/make_video.sh" Mjlab-StandUp-Flat-MicroDuck "$@"

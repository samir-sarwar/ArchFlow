#!/usr/bin/env bash
# Downloads a statically-compiled ffmpeg binary for Linux aarch64 (ARM64)
# and places it in the bin/ directory for use as a Lambda Layer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${SCRIPT_DIR}/bin"
FFMPEG_BIN="${BIN_DIR}/ffmpeg"

if [ -f "$FFMPEG_BIN" ]; then
  echo "ffmpeg binary already exists at ${FFMPEG_BIN}"
  exit 0
fi

mkdir -p "$BIN_DIR"

echo "Downloading static ffmpeg for linux-arm64..."
DOWNLOAD_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
TMPDIR=$(mktemp -d)

curl -sL "$DOWNLOAD_URL" -o "${TMPDIR}/ffmpeg.tar.xz"
tar -xf "${TMPDIR}/ffmpeg.tar.xz" -C "$TMPDIR"

# The archive contains a directory like ffmpeg-7.1-arm64-static/
cp "${TMPDIR}"/ffmpeg-*-arm64-static/ffmpeg "$FFMPEG_BIN"
chmod +x "$FFMPEG_BIN"

rm -rf "$TMPDIR"
echo "ffmpeg binary installed at ${FFMPEG_BIN}"

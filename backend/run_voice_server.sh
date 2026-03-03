#!/bin/bash
# ArchFlow Voice Server — convenience starter
# Usage: ./run_voice_server.sh [aws-profile]
#
# Refreshes SSO credentials, then starts the voice WebSocket server.
# The server will be available at ws://localhost:8081

set -e

PROFILE="${1:-archflow-sso}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Refreshing AWS SSO credentials for profile: ${PROFILE}"
aws sso login --profile "${PROFILE}"

echo "==> Starting ArchFlow voice server..."
cd "${SCRIPT_DIR}"
export BEDROCK_MODEL_SONIC="amazon.nova-2-sonic-v1:0"
voice_venv/bin/python -m voice_server.server --profile "${PROFILE}"

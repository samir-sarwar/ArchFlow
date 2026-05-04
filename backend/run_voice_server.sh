#!/bin/bash
# ArchFlow Voice Server — convenience starter
# Usage: ./run_voice_server.sh [aws-profile]
#
# Refreshes SSO credentials, then starts the voice WebSocket server.
# The server will be available at ws://localhost:8081

set -e

PROFILE="${1:-archflow-personal}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Starting ArchFlow voice server with profile: ${PROFILE}"
cd "${SCRIPT_DIR}"
export BEDROCK_MODEL_SONIC="amazon.nova-2-sonic-v1:0"
export CONVERSATION_TABLE_NAME="archflow-conversations-dev"
export UPLOADS_BUCKET="archflow-uploads-dev-285688017030"
voice_venv/bin/python -m voice_server.server --profile "${PROFILE}"

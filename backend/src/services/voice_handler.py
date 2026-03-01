import os
import subprocess

from src.services.bedrock_client import BedrockClient
from src.utils import logger

# Use the Lambda layer ffmpeg binary if available, otherwise system ffmpeg
_FFMPEG_BIN = "/opt/bin/ffmpeg" if os.path.exists("/opt/bin/ffmpeg") else "ffmpeg"

VOICE_SYSTEM_PROMPT = (
    "You are ArchFlow, a helpful software architecture design assistant. "
    "The user is speaking to you about software architecture. "
    "Listen carefully and respond with clear, concise architectural guidance. "
    "When discussing diagrams, describe components and relationships clearly."
)


def _convert_to_pcm(audio_bytes: bytes) -> bytes:
    """Convert audio bytes (WebM/OGG/MP4) to 16kHz mono 16-bit PCM via ffmpeg.

    Uses ffmpeg directly via subprocess — avoids pydub's ffprobe dependency.
    """
    result = subprocess.run(
        [
            _FFMPEG_BIN,
            "-i", "pipe:0",        # read from stdin
            "-f", "s16le",         # raw 16-bit signed little-endian PCM
            "-ar", "16000",        # 16kHz sample rate
            "-ac", "1",            # mono
            "pipe:1",              # write to stdout
        ],
        input=audio_bytes,
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr.decode()[:500]}")
    return result.stdout


async def process_voice_stream(
    audio_webm: bytes,
    session_id: str,
    bedrock_client: BedrockClient | None = None,
    on_transcription: "Callable[[str], None] | None" = None,
) -> dict:
    """
    Process voice input: convert WebM to PCM, transcribe via Nova Sonic.

    Args:
        audio_webm: Raw audio bytes in WebM/Opus format from the browser
        session_id: Unique conversation session ID
        bedrock_client: Shared BedrockClient instance (creates one if not provided)

    Returns:
        Dict with 'transcription', 'response_text', and 'audio_chunks'
    """
    logger.info(
        "Processing voice stream",
        extra={"session_id": session_id, "audio_size": len(audio_webm)},
    )

    # Convert to 16kHz mono 16-bit PCM (required by Nova Sonic)
    try:
        pcm_bytes = _convert_to_pcm(audio_webm)
    except Exception:
        logger.error("Failed to convert audio to PCM", exc_info=True)
        return {
            "transcription": "",
            "response_text": "",
            "audio_chunks": [],
            "error": "Audio format conversion failed. Please try a different browser or device.",
        }

    if not pcm_bytes:
        logger.warning("Audio conversion produced empty PCM data")
        return {
            "transcription": "",
            "response_text": "",
            "audio_chunks": [],
            "error": "Recording was empty. Please check your microphone and try again.",
        }

    duration_ms = len(pcm_bytes) // (16000 * 2) * 1000  # 16kHz, 16-bit = 2 bytes/sample
    logger.info(
        "Audio converted to PCM",
        extra={"pcm_size": len(pcm_bytes), "duration_ms": duration_ms},
    )

    # Process via Nova Sonic
    bedrock = bedrock_client or BedrockClient()
    try:
        result = await bedrock.invoke_sonic(
            audio_pcm=pcm_bytes,
            system_prompt=VOICE_SYSTEM_PROMPT,
            on_transcription=on_transcription,
        )
    except RuntimeError as e:
        logger.error("Nova Sonic invocation failed", exc_info=True)
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            return {
                "transcription": "",
                "response_text": "",
                "audio_chunks": [],
                "error": "Response generation timed out. Please try a shorter message.",
            }
        return {
            "transcription": "",
            "response_text": "",
            "audio_chunks": [],
            "error": "Speech processing failed. Please try again.",
        }
    except Exception:
        logger.error("Nova Sonic invocation failed", exc_info=True)
        return {
            "transcription": "",
            "response_text": "",
            "audio_chunks": [],
            "error": "Speech processing service is temporarily unavailable.",
        }

    logger.info(
        "Voice processing complete",
        extra={
            "session_id": session_id,
            "transcription_length": len(result.get("transcription", "")),
            "response_length": len(result.get("response_text", "")),
            "audio_chunks": len(result.get("audio_chunks", [])),
        },
    )

    return {
        "transcription": result.get("transcription", ""),
        "response_text": result.get("response_text", ""),
        "audio_chunks": result.get("audio_chunks", []),
    }

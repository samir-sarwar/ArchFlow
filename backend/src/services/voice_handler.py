import io

from pydub import AudioSegment

from src.services.bedrock_client import BedrockClient
from src.utils import logger

VOICE_SYSTEM_PROMPT = (
    "You are a helpful architecture design assistant. "
    "The user will speak to you about software architecture. "
    "Listen carefully and transcribe what they say accurately."
)


async def process_voice_stream(audio_webm: bytes, session_id: str) -> dict:
    """
    Process voice input: convert WebM to PCM, transcribe via Nova Sonic.

    Args:
        audio_webm: Raw audio bytes in WebM/Opus format from the browser
        session_id: Unique conversation session ID

    Returns:
        Dict with 'transcription' key containing the user's speech as text
    """
    logger.info(
        "Processing voice stream",
        extra={"session_id": session_id, "audio_size": len(audio_webm)},
    )

    # Convert WebM/Opus to 16kHz mono 16-bit PCM (required by Nova Sonic)
    audio = AudioSegment.from_file(io.BytesIO(audio_webm), format="webm")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    pcm_bytes = audio.raw_data

    logger.info(
        "Audio converted to PCM",
        extra={"pcm_size": len(pcm_bytes), "duration_ms": len(audio)},
    )

    # Transcribe via Nova Sonic
    bedrock = BedrockClient()
    result = await bedrock.invoke_sonic(
        audio_pcm=pcm_bytes,
        system_prompt=VOICE_SYSTEM_PROMPT,
    )

    logger.info(
        "Transcription complete",
        extra={
            "session_id": session_id,
            "transcription_length": len(result.get("transcription", "")),
        },
    )

    return {"transcription": result["transcription"]}

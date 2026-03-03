"""
Session manager for Amazon Nova 2 Sonic bidirectional streaming.

Adapted from:  amazon-nova-2-sonic/workshops/python-server/s2s_session_manager.py
Phase 2 fixes:
  - Removed auto-close from send_raw_event (was cancelling response_task prematurely)
  - close() no longer cancels response_task; instead closes input stream and lets
    _process_responses exit naturally via StopAsyncIteration
"""

import asyncio
import json
import os
import time
import warnings

from aws_sdk_bedrock_runtime.client import (
    BedrockRuntimeClient,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from aws_sdk_bedrock_runtime.config import Config
from aws_sdk_bedrock_runtime.models import (
    BidirectionalInputPayloadPart,
    InvokeModelWithBidirectionalStreamInputChunk,
)
from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver

from .s2s_events import S2sEvent

warnings.filterwarnings("ignore")

# For InvokeModelWithBidirectionalStream, use the DIRECT model ID — no "us." prefix.
# The "us." inference-profile prefix only works with the standard converse() API.
# Try nova-2-sonic first; fall back to nova-sonic if your account doesn't have nova-2-sonic access.
MODEL_ID = os.environ.get("BEDROCK_MODEL_SONIC", "amazon.nova-sonic-v1:0")

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


class S2sSessionManager:
    """Manages a single bidirectional Nova Sonic stream for one browser client."""

    def __init__(self, model_id=MODEL_ID, region=AWS_REGION):
        self.model_id = model_id
        self.region = region

        self.audio_input_queue: asyncio.Queue = asyncio.Queue()
        self.output_queue: asyncio.Queue = asyncio.Queue()

        self.response_task = None
        self.stream = None
        self.is_active = False
        self.bedrock_client = None

        self.prompt_name: str | None = None
        self.audio_content_name: str | None = None

        self._background_tasks: set = set()

    # ──────────────────────────── Lifecycle ────────────────────────────

    def _initialize_client(self):
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        )
        self.bedrock_client = BedrockRuntimeClient(config=config)

    async def initialize_stream(self):
        if not self.bedrock_client:
            self._initialize_client()

        self.stream = await self.bedrock_client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
        )
        self.is_active = True

        self.response_task = asyncio.create_task(self._process_responses())
        self._track(asyncio.create_task(self._process_audio_input()))

        await asyncio.sleep(0.1)
        return self

    async def close(self):
        """
        Gracefully tear down the stream.

        We close the INPUT stream (which causes Bedrock to close its end and
        triggers StopAsyncIteration in _process_responses), then wait briefly
        for the response task to exit naturally.
        We do NOT cancel response_task forcefully — that causes awscrt to raise
        InvalidStateError when its I/O thread tries to set_result on a cancelled Future.
        """
        if not self.is_active:
            return
        self.is_active = False

        # Cancel audio-input background tasks (safe — they just drain a queue)
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        # Close the Bedrock input stream; this signals the far end to close too
        if self.stream:
            try:
                await self.stream.input_stream.close()
            except Exception:
                pass

        # Let response_task exit cleanly via StopAsyncIteration (give it up to 5 s)
        if self.response_task and not self.response_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.response_task), timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass  # Best effort — don't crash

        self.stream = None
        self.response_task = None
        self.prompt_name = None
        self.audio_content_name = None

    def _track(self, task: asyncio.Task):
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    # ──────────────────────────── Sending ────────────────────────────

    async def send_raw_event(self, event_data: dict):
        """Serialize *event_data* dict and send it to the Bedrock stream."""
        if not self.stream or not self.is_active:
            return
        try:
            event_json = json.dumps(event_data)
            chunk = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=event_json.encode("utf-8"))
            )
            await self.stream.input_stream.send(chunk)
            # NOTE: we no longer auto-close on sessionEnd here.
            # The server decides when to close based on completionEnd from Bedrock.
        except Exception as e:
            print(f"[SessionManager] Error sending event: {e}")

    def add_audio_chunk(self, prompt_name: str, content_name: str, audio_data: str):
        """Enqueue a base64-encoded PCM audio chunk for async delivery."""
        self.audio_input_queue.put_nowait(
            {
                "prompt_name": prompt_name,
                "content_name": content_name,
                "audio_bytes": audio_data,
            }
        )

    # ──────────────────────────── Processing ────────────────────────────

    async def _process_audio_input(self):
        """Drain the audio queue and forward chunks to Bedrock."""
        while self.is_active:
            try:
                data = await self.audio_input_queue.get()
                prompt_name = data.get("prompt_name")
                content_name = data.get("content_name")
                audio_bytes = data.get("audio_bytes")

                if not (audio_bytes and prompt_name and content_name):
                    continue

                audio_event = S2sEvent.audio_input(
                    prompt_name,
                    content_name,
                    audio_bytes.decode("utf-8") if isinstance(audio_bytes, bytes) else audio_bytes,
                )
                await self.send_raw_event(audio_event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SessionManager] Audio processing error: {e}")

    async def _process_responses(self):
        """Read response events from Bedrock and put them on output_queue."""
        while True:
            try:
                output = await self.stream.await_output()
                result = await output[1].receive()

                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode("utf-8")
                    json_data = json.loads(response_data)
                    json_data["timestamp"] = int(time.time() * 1000)
                    await self.output_queue.put(json_data)

            except json.JSONDecodeError as ex:
                print(f"[SessionManager] JSON decode error: {ex}")
            except StopAsyncIteration:
                # Stream closed normally — signal consumers by putting a sentinel
                await self.output_queue.put({"_stream_ended": True})
                break
            except Exception as e:
                error_str = str(e)
                if "ValidationException" in error_str:
                    print(f"[SessionManager] Validation error: {error_str}")
                else:
                    print(f"[SessionManager] Response error: {error_str}")
                await self.output_queue.put({"_stream_ended": True, "_error": error_str})
                break

        self.is_active = False

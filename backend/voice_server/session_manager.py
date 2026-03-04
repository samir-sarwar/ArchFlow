"""
Session manager for Amazon Nova 2 Sonic bidirectional streaming.

Adapted from:  amazon-nova-2-sonic/workshops/python-server/s2s_session_manager.py
Phase 3: Added tool use handling for generateDiagram tool.
"""

import asyncio
import json
import logging
import os
import time
import uuid
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

from .diagram_tool import DiagramTool
from .s2s_events import S2sEvent

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# For InvokeModelWithBidirectionalStream, use the DIRECT model ID — no "us." prefix.
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
        self.current_diagram: str | None = None

        self._background_tasks: set = set()

        # Tool use state
        self.tool_use_content: dict = {}
        self.tool_use_id: str = ""
        self.tool_name: str = ""
        self.tool_processing_tasks: set = set()

        # Diagram tool — initialized lazily in initialize_stream
        self.diagram_tool: DiagramTool | None = None

        # Callback for sending diagram to frontend (set by server.py)
        self.on_diagram_generated = None

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

        # Initialize diagram tool
        self.diagram_tool = DiagramTool(region=self.region)

        self.response_task = asyncio.create_task(self._process_responses())
        self._track(asyncio.create_task(self._process_audio_input()))

        await asyncio.sleep(0.1)
        return self

    async def close(self):
        """Gracefully tear down the stream."""
        if not self.is_active:
            return
        self.is_active = False

        # Cancel tool processing tasks
        for task in list(self.tool_processing_tasks):
            if not task.done():
                task.cancel()
        if self.tool_processing_tasks:
            await asyncio.gather(*self.tool_processing_tasks, return_exceptions=True)
        self.tool_processing_tasks.clear()

        # Cancel audio-input background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        # Close the Bedrock input stream
        if self.stream:
            try:
                await self.stream.input_stream.close()
            except Exception:
                pass

        # Let response_task exit cleanly via StopAsyncIteration (up to 5s)
        if self.response_task and not self.response_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.response_task), timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass

        self.stream = None
        self.response_task = None
        self.prompt_name = None
        self.audio_content_name = None
        self.tool_use_content = {}
        self.tool_use_id = ""
        self.tool_name = ""

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
        except Exception as e:
            logger.error("Error sending event: %s", e)

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
                logger.error("Audio processing error: %s", e)

    async def _process_responses(self):
        """Read response events from Bedrock, detect tool use, put on output_queue."""
        while True:
            try:
                output = await self.stream.await_output()
                result = await output[1].receive()

                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode("utf-8")
                    json_data = json.loads(response_data)
                    json_data["timestamp"] = int(time.time() * 1000)

                    # Detect tool use events before putting on output queue
                    if "event" in json_data:
                        event_name = list(json_data["event"].keys())[0]

                        if event_name == "toolUse":
                            self.tool_use_content = json_data["event"]["toolUse"]
                            self.tool_name = json_data["event"]["toolUse"]["toolName"]
                            self.tool_use_id = json_data["event"]["toolUse"]["toolUseId"]
                            logger.info(
                                "Tool use detected: %s (id=%s)",
                                self.tool_name,
                                self.tool_use_id,
                            )

                        elif (
                            event_name == "contentEnd"
                            and json_data["event"]["contentEnd"].get("type") == "TOOL"
                        ):
                            logger.info("Tool content ended — spawning tool handler")
                            task = asyncio.create_task(
                                self._handle_tool_processing(
                                    self.prompt_name,
                                    self.tool_name,
                                    self.tool_use_content,
                                    self.tool_use_id,
                                )
                            )
                            self.tool_processing_tasks.add(task)
                            task.add_done_callback(self.tool_processing_tasks.discard)

                    await self.output_queue.put(json_data)

            except json.JSONDecodeError as ex:
                logger.error("JSON decode error: %s", ex)
            except StopAsyncIteration:
                await self.output_queue.put({"_stream_ended": True})
                break
            except Exception as e:
                error_str = str(e)
                if "ValidationException" in error_str:
                    logger.error("Validation error: %s", error_str)
                else:
                    logger.error("Response error: %s", error_str)
                await self.output_queue.put({"_stream_ended": True, "_error": error_str})
                break

        self.is_active = False

    # ──────────────────────────── Tool Processing ────────────────────────────

    async def _handle_tool_processing(
        self,
        prompt_name: str | None,
        tool_name: str,
        tool_use_content: dict,
        tool_use_id: str,
    ):
        """Process a tool call in the background without blocking event streaming."""
        try:
            logger.info("Processing tool: %s (id=%s)", tool_name, tool_use_id)

            if tool_name == "generateDiagram" and self.diagram_tool:
                # Extract the request from tool content
                content_str = tool_use_content.get("content", "{}")
                try:
                    parsed = json.loads(content_str) if isinstance(content_str, str) else content_str
                    request = parsed.get("request", content_str)
                except (json.JSONDecodeError, AttributeError):
                    request = str(content_str)

                result = await self.diagram_tool.generate(
                    request=request,
                    current_diagram=self.current_diagram,
                )

                # If diagram was generated, notify frontend
                if "diagram" in result and self.on_diagram_generated:
                    try:
                        await self.on_diagram_generated(result["diagram"])
                    except Exception as exc:
                        logger.error("Failed to send diagram to frontend: %s", exc)

                tool_result_str = json.dumps(result)
            else:
                tool_result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

            # Send tool result back to Bedrock
            if prompt_name and self.is_active:
                content_name = str(uuid.uuid4())

                await self.send_raw_event(
                    S2sEvent.content_start_tool(prompt_name, content_name, tool_use_id)
                )
                await self.send_raw_event(
                    S2sEvent.tool_result(prompt_name, content_name, tool_result_str)
                )
                await self.send_raw_event(
                    S2sEvent.content_end(prompt_name, content_name)
                )

                logger.info("Tool result sent to Bedrock for %s", tool_name)

        except Exception as e:
            logger.error("Tool processing error: %s", e, exc_info=True)

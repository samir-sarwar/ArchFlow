import asyncio
import base64
import json
import os
import uuid

import boto3

from src.utils import logger


class BedrockClient:
    """Wrapper for Amazon Bedrock API calls using the Converse API."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)

        # Nova 2 model IDs with the us. inference profile prefix (required for cross-region inference)
        # Note: Nova 2 only has Lite (text) and Sonic (speech) — there is no Pro tier.
        self.model_lite = os.environ.get("BEDROCK_MODEL_LITE", "us.amazon.nova-2-lite-v1:0")
        self.model_sonic = os.environ.get("BEDROCK_MODEL_SONIC", "us.amazon.nova-2-sonic-v1:0")

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: str = "",
        model_id: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Invoke a Bedrock model via the Converse API and return the response text."""
        model = model_id or self.model_lite

        logger.info("Invoking Bedrock model", extra={"model_id": model})

        kwargs = {
            "modelId": model,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "topP": 0.9, "temperature": 0.7},
        }

        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        last_exc = None
        retryable_error_codes = {"ThrottlingException", "ModelNotReadyException", "ServiceUnavailableException"}

        for attempt in range(2):
            try:
                response = self.client.converse(**kwargs)
                return response["output"]["message"]["content"][0]["text"]
            except Exception as e:
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
                is_retryable = error_code in retryable_error_codes or isinstance(
                    e, self.client.exceptions.ThrottlingException
                )

                if is_retryable:
                    logger.warning(
                        "Bedrock retryable error (attempt %d, model=%s, code=%s): %s",
                        attempt + 1, model, error_code, e,
                    )
                    last_exc = e
                    if attempt == 0:
                        await asyncio.sleep(2)
                    continue

                logger.error(
                    "Bedrock converse error (model=%s, code=%s): %s",
                    model, error_code, e, exc_info=True,
                )
                raise

        raise last_exc

    async def invoke_lite(self, prompt: str, system_prompt: str = "") -> str:
        """Invoke Nova Lite 2 for quick tasks."""
        return await self.invoke_model(
            prompt, system_prompt, model_id=self.model_lite, max_tokens=2048
        )

    async def invoke_lite_thinking(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        reasoning_effort: str = "medium",
    ) -> str:
        """Invoke Nova 2 Lite with thinking/reasoning mode enabled.

        reasoning_effort: "low", "medium", or "high".
        Note: "high" forbids temperature/topP/topK parameters.
        """
        model = self.model_lite
        logger.info(
            "Invoking Bedrock model with thinking",
            extra={"model_id": model, "reasoning_effort": reasoning_effort},
        )

        kwargs = {
            "modelId": model,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {},
            "additionalModelRequestFields": {
                "reasoningConfig": {
                    "type": "enabled",
                    "maxReasoningEffort": reasoning_effort,
                }
            },
        }

        # maxTokens, temperature, topP cannot be used with "high" effort
        if reasoning_effort != "high":
            kwargs["inferenceConfig"]["maxTokens"] = max_tokens
            kwargs["inferenceConfig"]["topP"] = 0.9
            kwargs["inferenceConfig"]["temperature"] = 0.7

        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        last_exc = None
        retryable_error_codes = {"ThrottlingException", "ModelNotReadyException", "ServiceUnavailableException"}

        for attempt in range(2):
            try:
                response = self.client.converse(**kwargs)
                # Thinking mode returns reasoningContent + text blocks; extract final text
                content_blocks = response["output"]["message"]["content"]
                for block in content_blocks:
                    if "text" in block:
                        return block["text"]

                # Model spent entire token budget on reasoning with no text output.
                # Retry without thinking mode — plain converse call usually succeeds
                # when the reasoning budget was the bottleneck.
                stop_reason = response.get("stopReason", "unknown")
                logger.warning(
                    "invoke_lite_thinking: no text block (stopReason=%s, blocks=%d) — "
                    "retrying without thinking mode",
                    stop_reason, len(content_blocks),
                )
                return await self.invoke_model(
                    prompt,
                    system_prompt=system_prompt,
                    model_id=self.model_lite,
                    max_tokens=4096,
                )
            except Exception as e:
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
                is_retryable = error_code in retryable_error_codes or isinstance(
                    e, self.client.exceptions.ThrottlingException
                )

                if is_retryable:
                    logger.warning(
                        "Bedrock retryable error (attempt %d, model=%s, code=%s): %s",
                        attempt + 1, model, error_code, e,
                    )
                    last_exc = e
                    if attempt == 0:
                        await asyncio.sleep(2)
                    continue

                logger.error(
                    "Bedrock converse error (model=%s, code=%s): %s",
                    model, error_code, e, exc_info=True,
                )
                raise

        raise last_exc

    async def invoke_with_image(
        self,
        image_b64: str,
        media_type: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Invoke Nova 2 Lite with an image for vision analysis."""
        logger.info("Invoking Bedrock with image", extra={"model_id": self.model_lite})

        fmt = media_type.split("/")[-1]
        if fmt == "jpg":
            fmt = "jpeg"

        # The Converse API accepts image bytes directly (no base64 wrapping needed)
        image_bytes = base64.b64decode(image_b64) if isinstance(image_b64, str) else image_b64

        kwargs = {
            "modelId": self.model_lite,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                        {"text": prompt},
                    ],
                }
            ],
            "inferenceConfig": {"maxTokens": max_tokens, "topP": 0.9, "temperature": 0.7},
        }

        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        response = self.client.converse(**kwargs)
        return response["output"]["message"]["content"][0]["text"]

    async def invoke_sonic_stream(self) -> "SonicStreamController":
        """Open a persistent bidirectional stream to Nova Sonic 2.

        Returns a SonicStreamController for incremental audio I/O.
        Used by the Lambda handler for one-shot interactions.
        For real-time streaming, use the voice_server/ module instead.
        """
        try:
            from aws_sdk_bedrock_runtime.client import (
                BedrockRuntimeClient as SonicClient,
                InvokeModelWithBidirectionalStreamOperationInput,
            )
            from aws_sdk_bedrock_runtime.config import Config as SonicConfig
            from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
        except ImportError as e:
            raise RuntimeError(
                f"Nova Sonic 2 SDK not available: {e}. "
                "Ensure aws-sdk-bedrock-runtime and smithy-aws-core are installed."
            ) from e

        config = SonicConfig(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        )
        sonic_client = SonicClient(config=config)

        stream = await sonic_client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_sonic)
        )

        return SonicStreamController(stream)


class SonicStreamController:
    """Wraps a Nova Sonic 2 bidirectional stream for real-time audio I/O."""

    def __init__(self, stream):
        self._stream = stream

    async def _send(self, event_dict: dict):
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )
        chunk = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(
                bytes_=json.dumps(event_dict).encode("utf-8")
            )
        )
        await self._stream.input_stream.send(chunk)

    async def send_session_start(self, max_tokens: int = 1024, top_p: float = 0.95, temperature: float = 0.7):
        await self._send({"event": {"sessionStart": {"inferenceConfiguration": {"maxTokens": max_tokens, "topP": top_p, "temperature": temperature}}}})

    async def send_prompt_start(self, prompt_name: str, voice_id: str = "tiffany"):
        await self._send({"event": {"promptStart": {"promptName": prompt_name, "textOutputConfiguration": {"mediaType": "text/plain"}, "audioOutputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": 24000, "sampleSizeBits": 16, "channelCount": 1, "voiceId": voice_id, "encoding": "base64", "audioType": "SPEECH"}}}})

    async def send_system_prompt(self, prompt_name: str, text: str):
        content_name = str(uuid.uuid4())
        await self._send({"event": {"contentStart": {"promptName": prompt_name, "contentName": content_name, "type": "TEXT", "interactive": False, "role": "SYSTEM", "textInputConfiguration": {"mediaType": "text/plain"}}}})
        await self._send({"event": {"textInput": {"promptName": prompt_name, "contentName": content_name, "content": text}}})
        await self._send({"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}})

    async def start_audio_input(self, prompt_name: str) -> str:
        content_name = str(uuid.uuid4())
        await self._send({"event": {"contentStart": {"promptName": prompt_name, "contentName": content_name, "type": "AUDIO", "interactive": True, "role": "USER", "audioInputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": 16000, "sampleSizeBits": 16, "channelCount": 1, "audioType": "SPEECH", "encoding": "base64"}}}})
        return content_name

    async def send_audio_chunk(self, prompt_name: str, content_name: str, pcm_base64: str):
        await self._send({"event": {"audioInput": {"promptName": prompt_name, "contentName": content_name, "content": pcm_base64}}})

    async def end_audio_input(self, prompt_name: str, content_name: str):
        await self._send({"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}})

    async def end_prompt(self, prompt_name: str):
        await self._send({"event": {"promptEnd": {"promptName": prompt_name}}})

    async def end_session(self):
        await self._send({"event": {"sessionEnd": {}}})

    async def close(self):
        try:
            await self._stream.input_stream.close()
        except Exception:
            pass

    async def response_events(self):
        """Async generator yielding parsed event dicts from the response stream."""
        try:
            while True:
                output = await self._stream.await_output()
                result = await output[1].receive()
                if result.value and result.value.bytes_:
                    data = json.loads(result.value.bytes_.decode("utf-8"))
                    if "event" in data:
                        yield data["event"]
        except StopAsyncIteration:
            pass

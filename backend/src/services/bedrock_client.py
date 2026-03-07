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

    async def invoke_pro(self, prompt: str, system_prompt: str = "") -> str:
        """Invoke Nova 2 Lite with higher token limit for complex reasoning.

        Note: Nova 2 has no Pro tier. This method uses Lite with max_tokens=4096.
        """
        return await self.invoke_model(
            prompt, system_prompt, model_id=self.model_lite, max_tokens=4096
        )

    async def invoke_with_image(
        self,
        image_b64: str,
        media_type: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Invoke Nova Pro 2 with an image for vision analysis."""
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

    async def invoke_pro_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ):
        """Invoke Nova Pro 2 with streaming — yields text chunks as they arrive."""
        kwargs = {
            "modelId": self.model_lite,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "topP": 0.9, "temperature": 0.7},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        response = self.client.converse_stream(**kwargs)
        stream = response.get("stream")
        if stream:
            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        yield delta["text"]

    async def invoke_sonic(
        self,
        audio_pcm: bytes,
        system_prompt: str = "",
        on_transcription: "Callable[[str], None] | None" = None,
    ) -> dict:
        """
        Invoke Nova Sonic 2 for speech-to-text and audio response.
        Returns dict with 'transcription', 'response_text', 'audio_chunks'.

        NOTE: This is the single-shot version (whole audio at once).
        For real-time streaming, the voice_server/ module is used instead.
        """
        from aws_sdk_bedrock_runtime.client import (
            BedrockRuntimeClient as SonicClient,
            InvokeModelWithBidirectionalStreamOperationInput,
        )
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )
        from aws_sdk_bedrock_runtime.config import Config as SonicConfig
        from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver

        logger.info("Invoking Nova Sonic (single-shot)", extra={"audio_size": len(audio_pcm)})

        prompt_name = str(uuid.uuid4())
        content_name = str(uuid.uuid4())
        audio_content_name = str(uuid.uuid4())

        config = SonicConfig(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        )
        sonic_client = SonicClient(config=config)

        async def _send_event(stream, event_dict: dict):
            chunk = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(
                    bytes_=json.dumps(event_dict).encode("utf-8")
                )
            )
            await stream.input_stream.send(chunk)

        stream = await sonic_client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_sonic)
        )

        user_texts = []
        assistant_texts = []
        audio_chunks = []
        current_role = None
        collection_error = None

        async def _collect_responses():
            nonlocal current_role, collection_error
            try:
                while True:
                    output = await stream.await_output()
                    result = await output[1].receive()
                    if result.value and result.value.bytes_:
                        data = json.loads(result.value.bytes_.decode("utf-8"))
                        if "event" not in data:
                            continue
                        evt = data["event"]
                        if "contentStart" in evt:
                            current_role = evt["contentStart"].get("role")
                        elif "textOutput" in evt:
                            text = evt["textOutput"]["content"]
                            if current_role == "USER":
                                user_texts.append(text)
                                if on_transcription:
                                    on_transcription(" ".join(user_texts))
                            elif current_role == "ASSISTANT":
                                assistant_texts.append(text)
                        elif "audioOutput" in evt:
                            audio_b64 = evt["audioOutput"].get("content", "")
                            if audio_b64:
                                audio_chunks.append(audio_b64)
                        elif "completionEnd" in evt:
                            break
            except StopAsyncIteration:
                pass
            except Exception as e:
                collection_error = e
                logger.error("Error collecting Sonic responses", exc_info=True)

        response_task = asyncio.create_task(_collect_responses())

        await _send_event(stream, {"event": {"sessionStart": {"inferenceConfiguration": {"maxTokens": 1024, "topP": 0.95, "temperature": 0.7}}}})
        await _send_event(stream, {"event": {"promptStart": {"promptName": prompt_name, "textOutputConfiguration": {"mediaType": "text/plain"}, "audioOutputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": 24000, "sampleSizeBits": 16, "channelCount": 1, "voiceId": "tiffany", "encoding": "base64", "audioType": "SPEECH"}}}})

        if system_prompt:
            await _send_event(stream, {"event": {"contentStart": {"promptName": prompt_name, "contentName": content_name, "type": "TEXT", "interactive": False, "role": "SYSTEM", "textInputConfiguration": {"mediaType": "text/plain"}}}})
            await _send_event(stream, {"event": {"textInput": {"promptName": prompt_name, "contentName": content_name, "content": system_prompt}}})
            await _send_event(stream, {"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}})

        await _send_event(stream, {"event": {"contentStart": {"promptName": prompt_name, "contentName": audio_content_name, "type": "AUDIO", "interactive": True, "role": "USER", "audioInputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": 16000, "sampleSizeBits": 16, "channelCount": 1, "audioType": "SPEECH", "encoding": "base64"}}}})

        chunk_size = 8192
        for i in range(0, len(audio_pcm), chunk_size):
            chunk = audio_pcm[i: i + chunk_size]
            await _send_event(stream, {"event": {"audioInput": {"promptName": prompt_name, "contentName": audio_content_name, "content": base64.b64encode(chunk).decode("utf-8")}}})

        await _send_event(stream, {"event": {"contentEnd": {"promptName": prompt_name, "contentName": audio_content_name}}})
        await _send_event(stream, {"event": {"promptEnd": {"promptName": prompt_name}}})
        await _send_event(stream, {"event": {"sessionEnd": {}}})
        await stream.input_stream.close()

        try:
            await asyncio.wait_for(response_task, timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("Nova Sonic response collection timed out after 60s")
            response_task.cancel()
            raise RuntimeError("Nova Sonic response collection timed out")

        if collection_error:
            raise collection_error

        return {
            "transcription": " ".join(user_texts).strip(),
            "response_text": " ".join(assistant_texts).strip(),
            "audio_chunks": audio_chunks,
        }

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

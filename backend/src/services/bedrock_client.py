import asyncio
import base64
import json
import os
import uuid

import boto3

from src.utils import logger


class BedrockClient:
    """Wrapper for Amazon Bedrock API calls."""

    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name="us-east-1")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.model_pro = os.environ.get("BEDROCK_MODEL_PRO", "us.amazon.nova-pro-v1:0")
        self.model_lite = os.environ.get(
            "BEDROCK_MODEL_LITE", "us.amazon.nova-lite-v1:0"
        )
        self.model_sonic = os.environ.get(
            "BEDROCK_MODEL_SONIC", "amazon.nova-sonic-v1:0"
        )

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: str = "",
        model_id: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Invoke a Bedrock model and return the response text."""
        model = model_id or self.model_pro

        logger.info("Invoking Bedrock model", extra={"model_id": model})

        body = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
        }

        if system_prompt:
            body["system"] = [{"text": system_prompt}]

        response = self.client.invoke_model(
            modelId=model,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["output"]["message"]["content"][0]["text"]

    async def invoke_lite(self, prompt: str, system_prompt: str = "") -> str:
        """Invoke Nova Lite for quick tasks."""
        return await self.invoke_model(
            prompt, system_prompt, model_id=self.model_lite, max_tokens=2048
        )

    async def invoke_pro(self, prompt: str, system_prompt: str = "") -> str:
        """Invoke Nova Pro for complex reasoning."""
        return await self.invoke_model(
            prompt, system_prompt, model_id=self.model_pro, max_tokens=4096
        )

    async def invoke_sonic(
        self, audio_pcm: bytes, system_prompt: str = ""
    ) -> dict:
        """Invoke Nova Sonic for speech-to-text transcription.

        Args:
            audio_pcm: Raw PCM audio bytes (16kHz, mono, 16-bit)
            system_prompt: System prompt for the conversation

        Returns:
            Dict with 'transcription' (user speech) and 'response_text' (assistant reply)
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

        logger.info("Invoking Nova Sonic", extra={"audio_size": len(audio_pcm)})

        prompt_name = str(uuid.uuid4())
        content_name = str(uuid.uuid4())
        audio_content_name = str(uuid.uuid4())

        # Initialize the experimental Bedrock client for bidirectional streaming
        config = SonicConfig(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        )
        sonic_client = SonicClient(config=config)

        async def _send_event(stream, event_json: str):
            event = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(
                    bytes_=event_json.encode("utf-8")
                )
            )
            await stream.input_stream.send(event)

        # Open the bidirectional stream
        stream = await sonic_client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(
                model_id=self.model_sonic
            )
        )

        user_texts = []
        assistant_texts = []
        current_role = None

        async def _collect_responses():
            nonlocal current_role
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
                            elif current_role == "ASSISTANT":
                                assistant_texts.append(text)

                        elif "completionEnd" in evt:
                            break

            except StopAsyncIteration:
                pass
            except Exception as e:
                logger.error("Error collecting Sonic responses", exc_info=True)

        # Start collecting responses in background
        response_task = asyncio.create_task(_collect_responses())

        # 1. Session start
        await _send_event(stream, json.dumps({
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 1024,
                        "topP": 0.9,
                        "temperature": 0.7,
                    }
                }
            }
        }))

        # 2. Prompt start
        await _send_event(stream, json.dumps({
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 24000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": "matthew",
                        "encoding": "base64",
                        "audioType": "SPEECH",
                    },
                }
            }
        }))

        # 3. System prompt
        if system_prompt:
            await _send_event(stream, json.dumps({
                "event": {
                    "contentStart": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "type": "TEXT",
                        "interactive": False,
                        "role": "SYSTEM",
                        "textInputConfiguration": {"mediaType": "text/plain"},
                    }
                }
            }))

            await _send_event(stream, json.dumps({
                "event": {
                    "textInput": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "content": system_prompt,
                    }
                }
            }))

            await _send_event(stream, json.dumps({
                "event": {
                    "contentEnd": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                    }
                }
            }))

        # 4. Audio input
        await _send_event(stream, json.dumps({
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 16000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64",
                    },
                }
            }
        }))

        # Send audio in chunks (8KB per chunk)
        chunk_size = 8192
        for i in range(0, len(audio_pcm), chunk_size):
            chunk = audio_pcm[i : i + chunk_size]
            audio_b64 = base64.b64encode(chunk).decode("utf-8")
            await _send_event(stream, json.dumps({
                "event": {
                    "audioInput": {
                        "promptName": prompt_name,
                        "contentName": audio_content_name,
                        "content": audio_b64,
                    }
                }
            }))

        # 5. End audio input
        await _send_event(stream, json.dumps({
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                }
            }
        }))

        # 6. End prompt
        await _send_event(stream, json.dumps({
            "event": {
                "promptEnd": {"promptName": prompt_name}
            }
        }))

        # 7. End session
        await _send_event(stream, json.dumps({
            "event": {"sessionEnd": {}}
        }))
        await stream.input_stream.close()

        # Wait for all responses to be collected
        await response_task

        transcription = " ".join(user_texts).strip()
        response_text = " ".join(assistant_texts).strip()

        logger.info(
            "Nova Sonic completed",
            extra={
                "transcription_length": len(transcription),
                "response_length": len(response_text),
            },
        )

        return {"transcription": transcription, "response_text": response_text}

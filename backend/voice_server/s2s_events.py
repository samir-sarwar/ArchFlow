"""
S2S (Speech-to-Speech) event builders for Amazon Nova 2 Sonic.

Adapted from:  amazon-nova-2-sonic/workshops/python-server/s2s_events.py
Changes:
  - Removed tool-use configurations (MCP, Strands, booking tools)
  - Set ArchFlow's architecture advisor system prompt as default
  - Configurable voice ID
"""

import json


ARCHFLOW_SYSTEM_PROMPT = (
    "You are ArchFlow, an expert AI software architect. "
    "You help users design and discuss software system architecture through natural conversation. "
    "Listen carefully to what the user says about their system and provide clear, expert guidance. "
    "When discussing components, services, databases, APIs, or architecture patterns, explain your "
    "reasoning concisely and ask clarifying questions when needed. "
    "Keep your spoken responses conversational and under 4–5 sentences so they feel natural when heard aloud."
)


class S2sEvent:
    """Factory methods for Nova Sonic bidirectional streaming events."""

    DEFAULT_INFER_CONFIG = {
        "maxTokens": 1024,
        "topP": 0.95,
        "temperature": 0.7,
    }

    DEFAULT_AUDIO_INPUT_CONFIG = {
        "mediaType": "audio/lpcm",
        "sampleRateHertz": 16000,
        "sampleSizeBits": 16,
        "channelCount": 1,
        "audioType": "SPEECH",
        "encoding": "base64",
    }

    DEFAULT_AUDIO_OUTPUT_CONFIG = {
        "mediaType": "audio/lpcm",
        "sampleRateHertz": 24000,
        "sampleSizeBits": 16,
        "channelCount": 1,
        "voiceId": "tiffany",
        "encoding": "base64",
        "audioType": "SPEECH",
    }

    @staticmethod
    def session_start(inference_config=None):
        if inference_config is None:
            inference_config = S2sEvent.DEFAULT_INFER_CONFIG
        return {"event": {"sessionStart": {"inferenceConfiguration": inference_config}}}

    @staticmethod
    def prompt_start(prompt_name, audio_output_config=None, tool_config=None):
        if audio_output_config is None:
            audio_output_config = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG
        event = {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": audio_output_config,
                    "toolUseOutputConfiguration": {"mediaType": "application/json"},
                }
            }
        }
        if tool_config:
            event["event"]["promptStart"]["toolConfiguration"] = tool_config
        return event

    @staticmethod
    def content_start_text(prompt_name, content_name, interactive=False, role="SYSTEM"):
        return {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "TEXT",
                    "interactive": interactive,
                    "role": role,
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        }

    @staticmethod
    def text_input(prompt_name, content_name, content=ARCHFLOW_SYSTEM_PROMPT):
        return {
            "event": {
                "textInput": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": content,
                }
            }
        }

    @staticmethod
    def content_end(prompt_name, content_name):
        return {
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                }
            }
        }

    @staticmethod
    def content_start_audio(prompt_name, content_name, audio_input_config=None):
        if audio_input_config is None:
            audio_input_config = S2sEvent.DEFAULT_AUDIO_INPUT_CONFIG
        return {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": audio_input_config,
                }
            }
        }

    @staticmethod
    def audio_input(prompt_name, content_name, content):
        return {
            "event": {
                "audioInput": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": content,
                }
            }
        }

    @staticmethod
    def prompt_end(prompt_name):
        return {"event": {"promptEnd": {"promptName": prompt_name}}}

    @staticmethod
    def session_end():
        return {"event": {"sessionEnd": {}}}

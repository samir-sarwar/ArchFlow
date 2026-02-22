import json
import os

import boto3

from src.utils import logger


class BedrockClient:
    """Wrapper for Amazon Bedrock API calls."""

    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name="us-east-1")
        self.model_pro = os.environ.get("BEDROCK_MODEL_PRO", "us.amazon.nova-pro-v1:0")
        self.model_lite = os.environ.get(
            "BEDROCK_MODEL_LITE", "us.amazon.nova-lite-v1:0"
        )
        self.model_sonic = os.environ.get(
            "BEDROCK_MODEL_SONIC", "us.amazon.nova-sonic-v2:0"
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

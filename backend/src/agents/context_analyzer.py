import base64
import json
import re

from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.services.file_processor import FileProcessor, UPLOADS_BUCKET
from src.utils import logger

CONTEXT_ANALYSIS_PROMPT = """You are an expert software architect analyzing a document for architectural context.

Extract and structure the following information from the document text:
1. **System Components**: Services, databases, APIs, queues, etc. mentioned
2. **Architecture Patterns**: Microservices, monolith, event-driven, etc.
3. **Technology Stack**: Languages, frameworks, cloud services mentioned
4. **Requirements**: Functional and non-functional requirements described
5. **Constraints**: Budget, team size, timeline, compliance requirements
6. **Data Flow**: How data moves between components

Return your analysis as structured JSON with these keys:
{
  "summary": "2-3 sentence summary of the document's architectural relevance",
  "components": ["list of components"],
  "patterns": ["list of patterns"],
  "technologies": ["list of technologies"],
  "requirements": {"functional": [...], "non_functional": [...]},
  "constraints": ["list of constraints"],
  "data_flows": ["description of each flow"]
}
"""

IMAGE_ANALYSIS_PROMPT = (
    "You are an expert at reading architecture diagrams and converting them "
    "to structured descriptions and Mermaid.js code."
)

# Max characters to send to the LLM
_MAX_TEXT_LENGTH = 50_000


class ContextAnalyzer:
    """Agent that processes uploaded documents and images for context."""

    def __init__(self, bedrock_client: BedrockClient | None = None):
        self.bedrock = bedrock_client or BedrockClient()
        self.file_processor = FileProcessor()

    async def process(self, context: ConversationContext) -> AgentResponse:
        """Analyze uploaded files and extract relevant context."""
        logger.info(
            "Context analyzer processing",
            extra={"session_id": context.session_id},
        )

        if not context.uploaded_files:
            return AgentResponse(
                text=(
                    "I don't see any uploaded files yet. You can upload PDFs, "
                    "images, or text files and I'll analyze them for "
                    "architectural context."
                ),
                agent_used="context_analyzer",
            )

        # Analyze the most recently uploaded file
        latest_file = context.uploaded_files[-1]
        file_key = latest_file.get("file_key", "")
        content_type = latest_file.get("content_type", "")

        try:
            if content_type.startswith("image/"):
                result = await self.analyze_image(file_key)
            else:
                result = await self.process_document(file_key, content_type)
        except Exception as e:
            logger.error("Context analysis failed", exc_info=True)
            return AgentResponse(
                text=f"I had trouble analyzing your file: {e}",
                agent_used="context_analyzer",
            )

        analysis = result.get("analysis", {})

        # Build summary text
        if isinstance(analysis, dict):
            summary = analysis.get("summary", str(analysis))
        else:
            summary = str(analysis)

        # Extract mermaid diagram if present (from image analysis)
        diagram_update = None
        if isinstance(analysis, str):
            mermaid_match = re.search(
                r"```mermaid\s*\n(.*?)```", analysis, re.DOTALL
            )
            if mermaid_match:
                diagram_update = mermaid_match.group(1).strip()

        return AgentResponse(
            text=(
                f"I've analyzed your uploaded document. Here's what I found:"
                f"\n\n{summary}"
            ),
            agent_used="context_analyzer",
            diagram_update=diagram_update,
            metadata={"file_analysis": analysis},
        )

    async def process_document(self, file_key: str, file_type: str) -> dict:
        """Extract and analyze document content from S3."""
        logger.info(
            "Processing document",
            extra={"file_key": file_key, "file_type": file_type},
        )

        result = await self.file_processor.process_upload(file_key, file_type)
        extracted_text = result["extracted_text"]

        # Truncate if extremely long
        if len(extracted_text) > _MAX_TEXT_LENGTH:
            extracted_text = (
                extracted_text[:_MAX_TEXT_LENGTH] + "\n\n[Document truncated...]"
            )

        prompt = (
            f"Analyze this document for architectural context:\n\n{extracted_text}"
        )

        response = await self.bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=CONTEXT_ANALYSIS_PROMPT,
        )

        # Parse JSON response with fallback
        analysis = self._parse_json_response(response)

        return {
            "file_key": file_key,
            "analysis": analysis,
            "text_length": len(extracted_text),
        }

    async def analyze_image(self, file_key: str) -> dict:
        """Analyze an uploaded diagram image via Nova Vision."""
        logger.info("Analyzing image", extra={"file_key": file_key})

        # Download image from S3
        response = self.file_processor.s3.get_object(
            Bucket=UPLOADS_BUCKET, Key=file_key
        )
        image_bytes = response["Body"].read()
        content_type = response.get("ContentType", "image/png")
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        analysis_text = await self.bedrock.invoke_with_image(
            image_b64=image_b64,
            media_type=content_type,
            prompt=(
                "Describe this architecture diagram. Identify all components, "
                "connections, data flows, and patterns. Also generate "
                "equivalent Mermaid.js syntax."
            ),
            system_prompt=IMAGE_ANALYSIS_PROMPT,
        )

        return {
            "file_key": file_key,
            "analysis": analysis_text,
        }

    @staticmethod
    def _parse_json_response(response: str) -> dict:
        """Parse an LLM response that should be JSON, with fallbacks."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Fall back to raw text
        return {"summary": response, "raw": True}

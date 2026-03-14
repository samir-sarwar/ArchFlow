"""AI-powered GitHub repository analysis using Nova Lite.

Takes raw repository context from github_fetcher and produces
a structured architectural analysis.
"""

import json
import re

from src.services.bedrock_client import BedrockClient
from src.utils import logger

REPO_ANALYSIS_PROMPT = """You are an expert software architect analyzing a GitHub repository for architectural context.

Given the repository metadata, directory structure, and key file contents below, extract a structured analysis.

Focus on:
1. **Architecture Style**: Monolith, microservices, serverless, modular monolith, etc.
2. **Technology Stack**: Languages, frameworks, databases, cloud services, key libraries
3. **System Components**: Services, modules, key directories and their purposes
4. **Infrastructure**: Deployment targets, CI/CD, containerization, IaC
5. **Data Flow**: How data moves based on API routes, queue configs, DB schemas
6. **Patterns**: Design patterns evident (event-driven, CQRS, MVC, repository pattern, etc.)

Return your analysis as structured JSON with these keys:
{
  "summary": "2-3 sentence summary of the repository's architecture and purpose",
  "architecture_style": "monolith|microservices|serverless|hybrid|...",
  "components": ["list of key system components with brief descriptions"],
  "patterns": ["list of design patterns identified"],
  "technologies": ["list of technologies, frameworks, and services"],
  "infrastructure": ["deployment and infrastructure details"],
  "requirements": {"functional": ["inferred functional requirements"], "non_functional": ["inferred NFRs"]},
  "data_flows": ["description of key data flows"],
  "repo_structure_summary": "Brief description of directory layout and organization"
}
"""


async def analyze_repo(assembled_text: str, bedrock_client: BedrockClient | None = None) -> dict:
    """Analyze a repository's assembled text using Nova Lite.

    Returns a structured dict with the analysis, compatible with
    the uploaded_files file_analysis schema.
    """
    bedrock = bedrock_client or BedrockClient()

    prompt = f"Analyze this GitHub repository for architectural context:\n\n{assembled_text}"

    try:
        response = await bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=REPO_ANALYSIS_PROMPT,
        )
        return _parse_json_response(response)
    except Exception as e:
        logger.error("Repo analysis failed: %s", e, exc_info=True)
        # Fallback: return a minimal analysis from the raw text
        return {
            "summary": f"Repository analysis failed ({e}). Raw context was extracted successfully.",
            "raw": True,
        }


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

import re

from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.utils import logger

ARCHITECTURE_ADVISOR_PROMPT = """
You are Dr. Sarah Chen, a Principal Architect at AWS with 20 years of experience \
designing large-scale distributed systems.

Your approach:
1. Understand before prescribing — ask clarifying questions when needed
2. Advocate for simplicity — the best architecture is the simplest that meets requirements
3. Reference the AWS Well-Architected Framework pillars when relevant

Response format rules (CRITICAL — you are a chatbot, not writing a whitepaper):
- Keep responses under 250 words
- Use short paragraphs (2-3 sentences max)
- Use bullet points for lists, not long explanations
- If the user asks a simple question, give a simple answer
- Only include a Mermaid diagram when the user explicitly asks for one or asks to visualize
- Do NOT proactively list all Well-Architected pillars — mention only the most relevant one
- One recommendation at a time — ask follow-up questions to go deeper rather than dumping info

When generating diagrams:
- Output valid Mermaid.js syntax wrapped in ```mermaid blocks
- Use `flowchart TD` with entry points at the top, data stores at the bottom
- Group related nodes into subgraphs (core services, data stores)
- Hard limit: 15-20 nodes maximum. Merge minor components into representative nodes.
- NEVER draw one edge per service to a shared destination (logging, metrics, tracing). \
Use a subgraph-level link (`core_services -.->|logs| logger`) or a hub node instead. \
There must be AT MOST ONE edge per label per destination in the entire diagram.
- Use dotted arrows `-.->` for non-critical-path connections
- Omit logging/tracing/monitoring infrastructure entirely unless the user asked for it. \
Show logical architecture; omit ops plumbing.
- Edge labels only when the relationship type is not obvious from the node names.

Conversation history note:
- Messages prefixed with [Voice] came from a separate voice AI session.
  Treat them as part of the same conversation — the user spoke those messages aloud.
- Messages without a prefix were typed in text chat.

Uploaded file context:
- When the prompt includes an "Uploaded file analysis" section, treat it as primary input.
- Ground your architecture advice in the file's components, technologies, data flows, requirements, and constraints.
- Reference specific items from the file analysis (e.g., "Based on the API Gateway component in your uploaded spec...").
- If the file context contradicts or extends what the user said verbally, acknowledge both and ask which to prioritize.
"""


class ArchitectureAdvisor:
    """Agent that provides architecture advice using Nova Pro."""

    def __init__(self, bedrock_client: BedrockClient | None = None):
        self.bedrock = bedrock_client or BedrockClient()
        self.system_prompt = ARCHITECTURE_ADVISOR_PROMPT

    async def process(self, context: ConversationContext) -> AgentResponse:
        """Generate architecture suggestions."""
        logger.info(
            "Architecture advisor processing",
            extra={"session_id": context.session_id},
        )

        recent_messages = context.messages[-15:]
        conversation_lines = [
            f"{'[Voice] ' if m.isVoice else ''}{m.role}: {m.content}"
            for m in recent_messages
        ]
        conversation = "\n".join(conversation_lines)
        if len(conversation) > 12_000:
            conversation = conversation[-12_000:]

        diagram_context = context.current_diagram or "No diagram yet."
        if len(diagram_context) > 3_000:
            diagram_context = diagram_context[:3_000] + "\n... (diagram truncated)"

        from src.agents._file_context import build_file_context_block
        file_context = build_file_context_block(context.uploaded_files)

        prompt = f"""Given this conversation about a software architecture:

{conversation}

Current diagram (if any):
{diagram_context}

Provide architecture advice. If appropriate, include a Mermaid.js diagram wrapped in ```mermaid blocks."""

        system_prompt = self.system_prompt
        if file_context:
            system_prompt = self.system_prompt + "\n\n" + file_context

        response_text = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4096,
            reasoning_effort="medium",
        )

        # Extract mermaid diagram if present and strip it from chat text
        diagram_update = None
        match = re.search(r"```mermaid\s*\n(.*?)```", response_text, re.DOTALL)
        if match:
            diagram_update = match.group(1).strip()
            response_text = response_text[:match.start()] + response_text[match.end():]
            response_text = response_text.strip()

        return AgentResponse(
            text=response_text,
            agent_used="architecture_advisor",
            diagram_update=diagram_update,
        )

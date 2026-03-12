import os
import boto3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class VoiceSessionDBClient:
    """Minimal DynamoDB client for the Voice Server to read/write shared context."""

    def __init__(self, region_name: str | None = None):
        self.table_name = os.environ.get("CONVERSATION_TABLE_NAME", "archflow-conversations-dev")
        region = region_name or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(self.table_name)

    def get_session_history(self, session_id: str) -> list[dict]:
        """Retrieve past messages for a given session."""
        try:
            response = self.table.get_item(Key={"session_id": session_id})
            if "Item" in response:
                return response["Item"].get("messages", [])
            return []
        except Exception as exc:
            logger.error("Failed to fetch session history for %s: %s", session_id, exc)
            return []

    def get_uploaded_files(self, session_id: str) -> list[dict]:
        """Retrieve uploaded file metadata (including analysis) for a session."""
        try:
            response = self.table.get_item(
                Key={"session_id": session_id},
                ProjectionExpression="uploaded_files",
            )
            if "Item" in response:
                files = response["Item"].get("uploaded_files", [])
                analyzed = [f for f in files if f.get("file_analysis")]
                logger.info(
                    "get_uploaded_files(%s): %d files, %d with analysis (table=%s)",
                    session_id, len(files), len(analyzed), self.table_name,
                )
                return files
            logger.info(
                "get_uploaded_files(%s): no session item found in table %s",
                session_id, self.table_name,
            )
            return []
        except Exception as exc:
            logger.error(
                "FAILED to fetch uploaded files for %s from table %s: %s",
                session_id, self.table_name, exc,
            )
            return []

    def append_voice_interaction(self, session_id: str, user_text: str, ai_text: str, is_voice: bool = True) -> None:
        """Append a voice/text interaction (user transcript + AI response) to DynamoDB."""
        if not user_text and not ai_text:
            return  # Nothing to save

        now = datetime.utcnow().isoformat()
        messages_to_add = []

        if user_text:
            msg = {
                "role": "user",
                "content": user_text,
                "timestamp": now,
            }
            if is_voice:
                msg["isVoice"] = True
            messages_to_add.append(msg)

        if ai_text:
            msg = {
                "role": "assistant",
                "content": ai_text,
                "timestamp": now,
                "agent": "voice_assistant" if is_voice else "sonic_text",
            }
            if is_voice:
                msg["isVoice"] = True
            messages_to_add.append(msg)
            
        if not messages_to_add:
            return

        try:
            self.table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET #msgs = list_append(if_not_exists(#msgs, :empty_list), :new_msgs), #la = :now",
                ExpressionAttributeNames={
                    "#msgs": "messages",
                    "#la": "last_activity"
                },
                ExpressionAttributeValues={
                    ":new_msgs": messages_to_add,
                    ":empty_list": [],
                    ":now": now
                }
            )
            logger.info("Saved %d messages to DynamoDB for session %s", len(messages_to_add), session_id)
        except Exception as exc:
            logger.error("Failed to append voice interaction for %s: %s", session_id, exc)

    def save_diagram(self, session_id: str, diagram_syntax: str) -> None:
        """Persist the current diagram so the text AI can load it from DynamoDB."""
        try:
            now = datetime.utcnow().isoformat()
            self.table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET current_diagram = :diagram, #la = :now",
                ExpressionAttributeNames={"#la": "last_activity"},
                ExpressionAttributeValues={":diagram": diagram_syntax, ":now": now},
            )
            logger.info("Saved diagram to DynamoDB for session %s", session_id)
        except Exception as exc:
            logger.error("Failed to save diagram for %s: %s", session_id, exc)

import os
import uuid
from datetime import datetime, timedelta

import boto3

from src.models import ConversationContext, DiagramVersion, Message
from src.utils import SessionExpiredError, SessionNotFoundError, logger

SESSION_TIMEOUT_MINUTES = 30


class ConversationStateManager:
    """Manages conversation state in DynamoDB."""

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        table_name = os.environ.get(
            "CONVERSATION_TABLE_NAME", "archflow-conversations-dev"
        )
        self.table = dynamodb.Table(table_name)

    async def create_session(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        title: str | None = None,
    ) -> str:
        """Create a new conversation session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        item = {
            "session_id": session_id,
            "created_at": now,
            "last_activity": now,
            "messages": [],
            "current_diagram": None,
            "diagram_versions": [],
            "uploaded_files": [],
            "metadata": {"requirements": {}, "architecture_decisions": []},
        }
        if user_id:
            item["user_id"] = user_id
        if title:
            item["title"] = title

        self.table.put_item(Item=item)

        logger.info("Session created", extra={"session_id": session_id, "user_id": user_id})
        return session_id

    async def get_session(self, session_id: str) -> ConversationContext:
        """Retrieve conversation state."""
        response = self.table.get_item(
            Key={"session_id": session_id}, ConsistentRead=True
        )

        if "Item" not in response:
            raise SessionNotFoundError(session_id)

        item = response["Item"]

        # Skip timeout for authenticated sessions
        if not item.get("user_id"):
            last_activity = datetime.fromisoformat(item["last_activity"])
            if datetime.utcnow() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                raise SessionExpiredError()

        return ConversationContext(**item)

    async def update_session(self, session_id: str, updates: dict) -> None:
        """Update session state."""
        updates["last_activity"] = datetime.utcnow().isoformat()

        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_names = {f"#{k}": k for k in updates}
        expr_values = {f":{k}": v for k, v in updates.items()}

        self.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )

    async def add_message(self, session_id: str, message: Message) -> None:
        """Append a message to the conversation history."""
        self.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET #msgs = list_append(#msgs, :msg), #la = :now",
            ExpressionAttributeNames={"#msgs": "messages", "#la": "last_activity"},
            ExpressionAttributeValues={
                ":msg": [message.model_dump()],
                ":now": datetime.utcnow().isoformat(),
            },
        )

    async def save_diagram_version(
        self, session_id: str, syntax: str, description: str | None = None
    ) -> None:
        """Save a new diagram version."""
        context = await self.get_session(session_id)
        version_num = len(context.diagram_versions) + 1

        version = DiagramVersion(
            version=version_num, syntax=syntax, description=description
        )

        self.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression=(
                "SET current_diagram = :diagram, "
                "diagram_versions = list_append(if_not_exists(diagram_versions, :empty_list), :ver), "
                "last_activity = :now"
            ),
            ExpressionAttributeValues={
                ":diagram": syntax,
                ":ver": [version.model_dump()],
                ":now": datetime.utcnow().isoformat(),
                ":empty_list": [],
            },
        )

    async def update_title(self, session_id: str, title: str) -> None:
        """Set the conversation title."""
        self.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET title = :t",
            ExpressionAttributeValues={":t": title},
        )

    async def list_user_conversations(self, user_id: str, limit: int = 50) -> list:
        """List conversations for a user, most recent first."""
        response = self.table.query(
            IndexName="user-conversations-index",
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            ScanIndexForward=False,
            Limit=limit,
        )
        return response.get("Items", [])

    async def delete_conversation(self, session_id: str, user_id: str) -> None:
        """Delete a conversation, verifying ownership."""
        response = self.table.get_item(Key={"session_id": session_id})
        if "Item" not in response:
            raise SessionNotFoundError(session_id)
        if response["Item"].get("user_id") != user_id:
            raise ValueError("Not authorized to delete this conversation")
        self.table.delete_item(Key={"session_id": session_id})

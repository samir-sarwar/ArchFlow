import os
import uuid
from datetime import datetime, timedelta

import bcrypt
import jwt
import boto3

from src.utils import logger

JWT_SECRET = os.environ.get("JWT_SECRET", "archflow-dev-jwt-secret-change-in-prod")
JWT_EXPIRY_HOURS = 24
JWT_ALGORITHM = "HS256"


class AuthService:
    """Handles user signup, login, and JWT verification."""

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        table_name = os.environ.get("USERS_TABLE_NAME", "archflow-users-dev")
        self.table = dynamodb.Table(table_name)

    def signup(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if not email or not password:
            raise ValueError("Email and password are required")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        existing = self.table.get_item(Key={"email": email})
        if "Item" in existing:
            raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        now = datetime.utcnow().isoformat()
        display_name = email.split("@")[0]

        self.table.put_item(Item={
            "email": email,
            "user_id": user_id,
            "password_hash": password_hash,
            "display_name": display_name,
            "created_at": now,
        })

        logger.info("User signed up", extra={"user_id": user_id, "email": email})
        token = self._generate_token(user_id, email)
        return {
            "token": token,
            "user_id": user_id,
            "email": email,
            "display_name": display_name,
        }

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if not email or not password:
            raise ValueError("Email and password are required")

        result = self.table.get_item(Key={"email": email})
        if "Item" not in result:
            raise ValueError("Invalid email or password")

        user = result["Item"]
        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            raise ValueError("Invalid email or password")

        logger.info("User logged in", extra={"user_id": user["user_id"], "email": email})
        token = self._generate_token(user["user_id"], email)
        return {
            "token": token,
            "user_id": user["user_id"],
            "email": email,
            "display_name": user.get("display_name", ""),
        }

    def verify_token(self, token: str) -> dict:
        """Returns {"user_id": ..., "email": ...} or raises ValueError."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return {"user_id": payload["user_id"], "email": payload["email"]}
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def _generate_token(self, user_id: str, email: str) -> str:
        return jwt.encode(
            {
                "user_id": user_id,
                "email": email,
                "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

import io
import os

import boto3
from pypdf import PdfReader

from src.utils import logger

UPLOADS_BUCKET = os.environ.get("UPLOADS_BUCKET", "archflow-uploads-dev")


class FileProcessor:
    """Handles file uploads and processing via S3."""

    def __init__(self):
        self.s3 = boto3.client("s3")

    def generate_presigned_upload_url(
        self, file_key: str, content_type: str, expires_in: int = 3600
    ) -> str:
        """Generate a presigned URL for file upload."""
        return self.s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": UPLOADS_BUCKET,
                "Key": file_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    async def extract_text(self, file_key: str) -> str:
        """Extract text from a document."""
        logger.info("Extracting text", extra={"file_key": file_key})

        extension = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""

        if extension == "pdf":
            return self._extract_pdf_text(file_key)
        elif extension == "txt":
            return self._read_text_file(file_key)
        else:
            raise ValueError(f"Unsupported file type: .{extension}")

    def _extract_pdf_text(self, file_key: str) -> str:
        """Extract text from a PDF using pypdf (pure Python, no AWS service needed)."""
        response = self.s3.get_object(Bucket=UPLOADS_BUCKET, Key=file_key)
        pdf_bytes = response["Body"].read()

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

        return "\n\n".join(pages)

    def _read_text_file(self, file_key: str) -> str:
        """Read a plain text file directly from S3."""
        response = self.s3.get_object(Bucket=UPLOADS_BUCKET, Key=file_key)
        return response["Body"].read().decode("utf-8")

    async def process_upload(self, file_key: str, file_type: str) -> dict:
        """Process an uploaded file and return extracted context."""
        logger.info(
            "Processing upload",
            extra={"file_key": file_key, "file_type": file_type},
        )

        extracted_text = await self.extract_text(file_key)

        return {
            "file_key": file_key,
            "file_type": file_type,
            "extracted_text": extracted_text,
            "character_count": len(extracted_text),
        }

import os
import time

import boto3

from src.utils import logger

UPLOADS_BUCKET = os.environ.get("UPLOADS_BUCKET", "archflow-uploads-dev")

# Max time to wait for Textract async job (seconds)
_TEXTRACT_POLL_TIMEOUT = 90
_TEXTRACT_POLL_INTERVAL = 2


class FileProcessor:
    """Handles file uploads and processing via S3 and Textract."""

    def __init__(self):
        self.s3 = boto3.client("s3")
        self.textract = boto3.client("textract")

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
        """Extract text from a document using Textract or direct read."""
        logger.info("Extracting text", extra={"file_key": file_key})

        extension = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""

        if extension in ("png", "jpg", "jpeg"):
            return self._extract_image_text(file_key)
        elif extension == "pdf":
            return self._extract_pdf_text(file_key)
        elif extension == "txt":
            return self._read_text_file(file_key)
        else:
            raise ValueError(f"Unsupported file type: .{extension}")

    def _extract_image_text(self, file_key: str) -> str:
        """Extract text from a single image using synchronous Textract."""
        response = self.textract.detect_document_text(
            Document={"S3Object": {"Bucket": UPLOADS_BUCKET, "Name": file_key}}
        )
        return self._blocks_to_text(response["Blocks"])

    def _extract_pdf_text(self, file_key: str) -> str:
        """Extract text from a PDF using async Textract (supports multi-page)."""
        job = self.textract.start_document_text_detection(
            DocumentLocation={
                "S3Object": {"Bucket": UPLOADS_BUCKET, "Name": file_key}
            }
        )
        job_id = job["JobId"]
        logger.info("Started Textract job", extra={"job_id": job_id})

        # Poll for completion
        elapsed = 0
        while elapsed < _TEXTRACT_POLL_TIMEOUT:
            result = self.textract.get_document_text_detection(JobId=job_id)
            status = result["JobStatus"]

            if status == "SUCCEEDED":
                break
            elif status == "FAILED":
                raise RuntimeError(
                    f"Textract job failed: {result.get('StatusMessage', 'unknown error')}"
                )

            time.sleep(_TEXTRACT_POLL_INTERVAL)
            elapsed += _TEXTRACT_POLL_INTERVAL
        else:
            raise RuntimeError("Textract job timed out")

        # Collect all pages
        all_text = self._blocks_to_text(result["Blocks"])
        next_token = result.get("NextToken")
        while next_token:
            result = self.textract.get_document_text_detection(
                JobId=job_id, NextToken=next_token
            )
            all_text += "\n" + self._blocks_to_text(result["Blocks"])
            next_token = result.get("NextToken")

        return all_text

    def _read_text_file(self, file_key: str) -> str:
        """Read a plain text file directly from S3."""
        response = self.s3.get_object(Bucket=UPLOADS_BUCKET, Key=file_key)
        return response["Body"].read().decode("utf-8")

    @staticmethod
    def _blocks_to_text(blocks: list) -> str:
        """Extract LINE-type blocks from Textract output into plain text."""
        return "\n".join(
            block["Text"] for block in blocks if block["BlockType"] == "LINE"
        )

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

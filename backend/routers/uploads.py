from fastapi import APIRouter, Depends, HTTPException
import aioboto3
import uuid

from config import BUCKET_NAME
from db.database import get_aws_client
from schemas.models import ImageUploadSignURL
from db.models import User
from routers.auth import get_current_user_from_token

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/image-upload-url")
async def generate_image_upload_url(
    data: ImageUploadSignURL,
    current_user: User = Depends(get_current_user_from_token),
    aws_client: aioboto3.Session = Depends(get_aws_client),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_key = f"image_uploads/{uuid.uuid4()}"
    try:
        async with aws_client.client("s3") as s3:
            presigned_url = await s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": BUCKET_NAME,
                    "Key": file_key,
                    "ContentType": data.content_type,
                },
                ExpiresIn=3600,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "upload_url": presigned_url,
        "file_key": file_key,
        "url": f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_key}",
    }

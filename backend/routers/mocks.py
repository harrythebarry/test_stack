from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from config import UNSPLASH_ACCESS_KEY
import httpx

router = APIRouter(prefix="/api/mocks", tags=["mocks"])


@router.get("/images")
async def get_random_image(orientation, query):
    params = {
        "client_id": UNSPLASH_ACCESS_KEY,
    }
    if query:
        params["query"] = query
    if orientation in ["landscape", "portrait", "squarish"]:
        params["orientation"] = orientation

    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.unsplash.com/photos/random", params=params)

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code, detail="Failed to fetch image"
            )

        data = resp.json()
        image_url = data["urls"][
            "regular"
        ]  # You can also use "raw", "full", or "small"
        return RedirectResponse(url=image_url)

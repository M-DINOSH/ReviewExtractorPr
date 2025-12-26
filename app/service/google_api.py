import httpx
import asyncio
from typing import Dict, Any

MAX_RETRIES = 3


async def google_get(url: str, access_token: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            resp = await client.get(url, headers=headers)
            print(f"res : {resp}")
            # 🔍 Always log Google response
            print("Google status:", resp.status_code)
            print("Google body:", resp.text)

            # ---------- RATE LIMIT ----------
            if resp.status_code == 429:
                if attempt == MAX_RETRIES:
                    return {
                        "error": "RATE_LIMITED",
                        "message": "Quota = 0 or exceeded",
                        "details": resp.text,
                    }
                await asyncio.sleep(30)
                continue

            # ---------- AUTH ----------
            if resp.status_code in (401, 403):
                return {
                    "error": "AUTH_ERROR",
                    "status": resp.status_code,
                    "details": resp.json(),
                }

            # ---------- OTHER ERRORS ----------
            if resp.status_code >= 400:
                return {
                    "error": "GOOGLE_API_ERROR",
                    "status": resp.status_code,
                    "details": resp.json(),
                }

            return resp.json()

    return {
        "error": "UNKNOWN_ERROR",
        "message": "Unexpected Google API failure",
    }

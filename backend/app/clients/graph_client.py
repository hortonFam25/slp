from typing import Optional
import httpx


class GraphClient:
    def __init__(self, access_token: str):
        self._client = httpx.AsyncClient(
            base_url="https://graph.microsoft.com/v1.0",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

    async def me(self) -> dict:
        res = await self._client.get("/me")
        res.raise_for_status()
        return res.json()

    async def search_mail(self, query: str, top: int = 10) -> dict:
        res = await self._client.get(f"/me/messages?$search=\"{query}\"&$top={top}")
        res.raise_for_status()
        return res.json()

    async def aclose(self):
        await self._client.aclose()



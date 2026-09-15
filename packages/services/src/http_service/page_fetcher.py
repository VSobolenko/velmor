from __future__ import annotations

import httpx
from bs4 import BeautifulSoup


class PageFetcher:
    """Fetch the readable text of a landing page.

    Rights statements live in prose on the item's own page, so the agent needs
    text rather than markup. Script and style content is dropped because it is
    noise that wastes context and occasionally contains misleading strings.
    """

    MAX_CHARACTERS = 20000

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_text(self, url: str) -> str:
        response = await self._http.get(url, follow_redirects=True)
        response.raise_for_status()
        return self._to_text(response.text)

    def _to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(('script', 'style', 'noscript')):
            tag.decompose()
        text = ' '.join(soup.get_text(separator=' ').split())
        return text[: self.MAX_CHARACTERS]

import os
import requests
from typing import Dict, List


class SerperSearchService:
    """SERPER.dev Google Search API integration."""

    URL = "https://google.serper.dev/search"

    def __init__(self, config: Dict):
        self.api_key = os.getenv("SERPER_API_KEY")
        if not self.api_key:
            raise RuntimeError("SERPER_API_KEY not set.")
        self.max_results = config.get("max_results", 5)

    def search(self, query: str) -> List[Dict]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        response = requests.post(
            self.URL,
            headers=headers,
            json={"q": query, "num": self.max_results},
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()

        return [
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            }
            for item in data.get("organic", [])[: self.max_results]
        ]

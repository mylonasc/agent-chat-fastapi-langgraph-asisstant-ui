import os
from unittest.mock import patch
from tools.web_search.service import SerperSearchService


@patch("tools.web_search.service.requests.post")
def test_serper_parsing(mock_post):
    os.environ["SERPER_API_KEY"] = "test"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "organic": [{"title": "Test", "link": "http://a.com", "snippet": "desc"}]
    }

    service = SerperSearchService({"max_results": 1})
    results = service.search("query")

    assert len(results) == 1
    assert results[0]["title"] == "Test"

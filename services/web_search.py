import asyncio
from typing import Optional
import httpx
from bs4 import BeautifulSoup


REDDIT_SEARCH_URL = "https://www.reddit.com/r/mtgrules/search.json"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"
MIN_REDDIT_SCORE = 2
MAX_RESULTS = 5


async def search_reddit(
    query: str,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Search r/mtgrules for relevant posts. Returns list of {title, body, url, score}."""
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        should_close = True

    try:
        response = await client.get(
            REDDIT_SEARCH_URL,
            params={
                "q": query,
                "restrict_sr": "on",
                "sort": "relevance",
                "limit": "5",
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        children = data.get("data", {}).get("children", [])

        results = []
        for child in children:
            post = child.get("data", {})
            score = post.get("score", 0)
            if score < MIN_REDDIT_SCORE:
                continue
            results.append({
                "source": "reddit",
                "title": post.get("title", ""),
                "snippet": post.get("selftext", "")[:300],
                "url": f"https://www.reddit.com{post.get('permalink', '')}",
                "score": score,
            })

        return results[:MAX_RESULTS]
    except Exception:
        return []
    finally:
        if should_close:
            await client.aclose()


async def search_ddg(
    query: str,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Search DuckDuckGo HTML for MTG rules info. Returns list of {title, snippet, url}."""
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        should_close = True

    try:
        response = await client.get(
            DDG_HTML_URL,
            params={"q": f"mtg rules {query}"},
        )

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result_div in soup.select(".result"):
            link_tag = result_div.select_one(".result__a")
            snippet_tag = result_div.select_one(".result__snippet")

            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            url = link_tag.get("href", "")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            if title and url:
                results.append({
                    "source": "ddg",
                    "title": title,
                    "snippet": snippet[:300],
                    "url": url,
                })

        return results[:MAX_RESULTS]
    except Exception:
        return []
    finally:
        if should_close:
            await client.aclose()


async def fallback_search(
    query: str,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Run Reddit + DuckDuckGo searches concurrently and combine results."""
    reddit_results, ddg_results = await asyncio.gather(
        search_reddit(query, client=client),
        search_ddg(query, client=client),
        return_exceptions=True,
    )

    # Handle any exceptions from gather
    if isinstance(reddit_results, Exception):
        reddit_results = []
    if isinstance(ddg_results, Exception):
        ddg_results = []

    # Reddit first (typically higher quality), then DDG
    combined = list(reddit_results) + list(ddg_results)
    return combined[:MAX_RESULTS]

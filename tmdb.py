from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final, Optional

import httpx
from cachetools import TTLCache
from decouple import config

TMDB_API_KEY: Final = config("TMDB_API_KEY", cast=str)
TMDB_BASE: Final = "https://api.themoviedb.org/3"
TMDB_IMG_THUMB: Final = "https://image.tmdb.org/t/p/w185"
TMDB_IMG_FULL: Final = "https://image.tmdb.org/t/p/w500"

_cache: TTLCache = TTLCache(maxsize=256, ttl=3600)
_cache_lock = asyncio.Lock()
_details_cache: TTLCache = TTLCache(maxsize=512, ttl=86400)  # Cache details for 24 hours
_details_cache_lock = asyncio.Lock()
_client: Optional[httpx.AsyncClient] = None


@dataclass
class Movie:
    id: int
    title: str
    release_date: str
    overview: str
    vote_average: float
    runtime: Optional[int]
    poster_url_thumb: Optional[str]
    poster_url_full: Optional[str]


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=TMDB_BASE, timeout=10.0)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def fetch_movie_details(movie_id: int) -> dict:
    async with _details_cache_lock:
        cached = _details_cache.get(movie_id)
    if cached is not None:
        return cached

    r = await _get_client().get(
        f"/movie/{movie_id}",
        params={
            "api_key": TMDB_API_KEY,
        },
    )
    r.raise_for_status()
    data = r.json()

    async with _details_cache_lock:
        _details_cache[movie_id] = data
    return data


async def search_movies(query: str) -> list[Movie]:
    key = query.lower().strip()
    if not key:
        return []

    async with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    r = await _get_client().get(
        "/search/movie",
        params={
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": False,
        },
    )
    r.raise_for_status()
    data = r.json()

    results = data.get("results", [])
    
    # First, create Movie objects without runtime
    movies = []
    for item in results:
        movies.append(
            Movie(
                id=item["id"],
                title=item.get("title") or item.get("original_title") or "Unknown",
                release_date=item.get("release_date") or "",
                overview=item.get("overview") or "",
                vote_average=float(item.get("vote_average") or 0.0),
                runtime=None,
                poster_url_thumb=(TMDB_IMG_THUMB + item["poster_path"]) if item.get("poster_path") else None,
                poster_url_full=(TMDB_IMG_FULL + item["poster_path"]) if item.get("poster_path") else None,
            )
        )

    # Only fetch runtime for top 10 results in parallel
    top_movies = movies[:10]
    detail_tasks = [fetch_movie_details(m.id) for m in top_movies]
    
    try:
        details_list = await asyncio.gather(*detail_tasks, return_exceptions=True)
        for movie, details in zip(top_movies, details_list):
            if isinstance(details, Exception):
                movie.runtime = None
            else:
                movie.runtime = details.get("runtime")
    except Exception:
        pass  # If parallel fetch fails, runtime stays None

    async with _cache_lock:
        _cache[key] = movies
    return movies

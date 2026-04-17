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
class Media:
    id: int
    media_type: str  # "movie" or "tv"
    title: str
    release_date: str
    overview: str
    vote_average: float
    runtime: Optional[int]
    imdb_id: Optional[str]
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
        cached = _details_cache.get(f"movie_{movie_id}")
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
        _details_cache[f"movie_{movie_id}"] = data
    return data


async def fetch_tv_details(tv_id: int) -> dict:
    async with _details_cache_lock:
        cached = _details_cache.get(f"tv_{tv_id}")
    if cached is not None:
        return cached

    r = await _get_client().get(
        f"/tv/{tv_id}",
        params={
            "api_key": TMDB_API_KEY,
        },
    )
    r.raise_for_status()
    data = r.json()

    async with _details_cache_lock:
        _details_cache[f"tv_{tv_id}"] = data
    return data


async def search_media(query: str) -> list[Media]:
    key = query.lower().strip()
    if not key:
        return []

    async with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    # Search both movies and TV shows in parallel
    movie_task = _get_client().get(
        "/search/movie",
        params={
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": False,
        },
    )
    tv_task = _get_client().get(
        "/search/tv",
        params={
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": False,
        },
    )

    movie_response, tv_response = await asyncio.gather(movie_task, tv_task)
    movie_response.raise_for_status()
    tv_response.raise_for_status()

    movie_data = movie_response.json()
    tv_data = tv_response.json()

    media_items = []

    # Process movies
    for item in movie_data.get("results", []):
        media_items.append(
            Media(
                id=item["id"],
                media_type="movie",
                title=item.get("title") or item.get("original_title") or "Unknown",
                release_date=item.get("release_date") or "",
                overview=item.get("overview") or "",
                vote_average=float(item.get("vote_average") or 0.0),
                runtime=None,
                imdb_id=None,
                poster_url_thumb=(TMDB_IMG_THUMB + item["poster_path"]) if item.get("poster_path") else None,
                poster_url_full=(TMDB_IMG_FULL + item["poster_path"]) if item.get("poster_path") else None,
            )
        )

    # Process TV shows
    for item in tv_data.get("results", []):
        media_items.append(
            Media(
                id=item["id"],
                media_type="tv",
                title=item.get("name") or item.get("original_name") or "Unknown",
                release_date=item.get("first_air_date") or "",
                overview=item.get("overview") or "",
                vote_average=float(item.get("vote_average") or 0.0),
                runtime=None,
                imdb_id=None,
                poster_url_thumb=(TMDB_IMG_THUMB + item["poster_path"]) if item.get("poster_path") else None,
                poster_url_full=(TMDB_IMG_FULL + item["poster_path"]) if item.get("poster_path") else None,
            )
        )

    # Sort by vote average and take top 25
    media_items.sort(key=lambda x: x.vote_average, reverse=True)
    media_items = media_items[:25]

    # Fetch runtime for top 10 in parallel
    top_media = media_items[:10]
    detail_tasks = []
    for m in top_media:
        if m.media_type == "movie":
            detail_tasks.append(fetch_movie_details(m.id))
        else:
            detail_tasks.append(fetch_tv_details(m.id))

    try:
        details_list = await asyncio.gather(*detail_tasks, return_exceptions=True)
        for media, details in zip(top_media, details_list):
            if isinstance(details, Exception):
                media.runtime = None
                media.imdb_id = None
            else:
                if media.media_type == "movie":
                    media.runtime = details.get("runtime")
                    media.imdb_id = details.get("imdb_id")
                else:
                    # TV shows have episode_run_time as an array, take the first value
                    episode_runtimes = details.get("episode_run_time", [])
                    media.runtime = episode_runtimes[0] if episode_runtimes else None
                    # TV shows external_ids contains imdb_id
                    external_ids = details.get("external_ids", {})
                    media.imdb_id = external_ids.get("imdb_id")
    except Exception:
        pass  # If parallel fetch fails, runtime and imdb_id stay None

    async with _cache_lock:
        _cache[key] = media_items
    return media_items

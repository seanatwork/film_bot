from __future__ import annotations

import logging
from html import escape
from typing import Final

from decouple import config
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChosenInlineResultHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
)

from tmdb import Movie, close_client, search_movies

TOKEN: Final = config("TELEGRAM_TOKEN", cast=str)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Hi! I look up films from TMDb.\n\n"
        f"Type @{context.bot.username} <movie title> in any chat to search inline."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Inline usage:\n"
        f"  @{context.bot.username} <movie title>\n\n"
        f"Picking a result posts a large poster with title, year, runtime, rating, and overview."
    )


def _build_message(movie: Movie, max_len: int = 4096) -> str:
    year = movie.release_date[:4] if movie.release_date else "—"
    rating = f"{movie.vote_average:.1f}/10" if movie.vote_average else "N/A"
    runtime = f"{movie.runtime} min" if movie.runtime else "—"

    poster_line = f"{movie.poster_url_full}\n\n" if movie.poster_url_full else ""
    header = f"<b>{escape(movie.title)}</b> ({escape(year)})\n{runtime}\n⭐ {rating}\n\n"

    budget = max_len - len(poster_line) - len(header)
    overview = (movie.overview or "No overview available.").strip()
    if len(overview) > budget:
        overview = overview[: max(budget - 3, 0)] + "..."

    return poster_line + header + escape(overview)


async def inline_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.strip()
    if not query:
        return

    try:
        movies = await search_movies(query)
    except Exception:
        logger.exception("TMDb search failed for %r", query)
        await update.inline_query.answer([], cache_time=1)
        return

    results = []
    for m in movies[:25]:
        year = m.release_date[:4] if m.release_date else "—"
        rating = f"{m.vote_average:.1f}/10" if m.vote_average else "N/A"
        title = f"{m.title} ({year})"
        description_parts = [rating]
        if m.overview:
            description_parts.append(m.overview[:80])
        description = " · ".join(description_parts)

        results.append(
            InlineQueryResultArticle(
                id=str(m.id),
                title=title,
                description=description,
                thumbnail_url=m.poster_url_thumb,
                input_message_content=InputTextMessageContent(
                    message_text=_build_message(m),
                    parse_mode=ParseMode.HTML,
                ),
            )
        )

    logger.info("answering inline query %r with %d results", query, len(results))
    try:
        await update.inline_query.answer(results, cache_time=1)
    except Exception:
        logger.exception("inline_query.answer failed")


async def chosen_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cir = update.chosen_inline_result
    logger.info("chosen inline result id=%s query=%r user=%s", cir.result_id, cir.query, cir.from_user.id)


async def _shutdown(app: Application) -> None:
    await close_client()


def main() -> None:
    app = ApplicationBuilder().token(TOKEN).post_shutdown(_shutdown).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(InlineQueryHandler(inline_handle))
    app.add_handler(ChosenInlineResultHandler(chosen_result))
    app.run_polling()


if __name__ == "__main__":
    main()

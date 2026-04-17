# Film Bot

A Telegram inline bot that searches for movies and TV shows using The Movie Database (TMDb) API and displays information including title, year, runtime, rating, and overview.

## Features

- **Inline Search**: Type `@botname <title>` in any Telegram chat to search for movies and TV shows
- **Rich Information**: Displays title, year, runtime, rating, and overview
- **Poster Images**: Shows poster URL for easy viewing
- **Efficient API Usage**: Caches search results and media details to minimize API calls
- **Parallel Fetching**: Fetches media details in parallel for faster response times
- **Dual Search**: Searches both movies and TV shows simultaneously

## Prerequisites

- Python 3.12+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- TMDb API Key (from [The Movie Database](https://www.themoviedb.org/settings/api))

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd film_bot
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```
TELEGRAM_TOKEN=your_telegram_bot_token
TMDB_API_KEY=your_tmdb_api_key
```

## Running the Bot

Start the bot:
```bash
python bot.py
```

The bot will start polling and you can test it by typing `@your_bot_username <movie title>` in any Telegram chat.

## Deployment

### GitHub

1. Initialize git repository (if not already done):
```bash
git init
git add .
git commit -m "Initial commit"
```

2. Create a new repository on GitHub

3. Push to GitHub:
```bash
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

### Fly.io

1. Install the Fly.io CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Sign in to Fly.io:
```bash
fly auth login
```

3. Create a `Dockerfile` in the project root:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

4. Create a `fly.toml` configuration file:
```toml
app = "film-bot"

[build]
  dockerfile = "Dockerfile"

[env]
  TELEGRAM_TOKEN = ""
  TMDB_API_KEY = ""

[[services]]
  protocol = "tcp"
  internal_port = 8080

  [[services.ports]]
    port = 80
    handlers = ["http"]
```

5. Set environment variables on Fly.io:
```bash
fly secrets set TELEGRAM_TOKEN=your_token TMDB_API_KEY=your_key
```

6. Deploy to Fly.io:
```bash
fly launch
fly deploy
```

## API Usage

The bot is optimized to minimize API calls:
- Search results are cached for 1 hour
- Movie details (runtime) are cached for 24 hours
- Only fetches runtime for top 10 results
- Uses parallel fetching for faster response times

## License

MIT

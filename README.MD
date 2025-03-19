# Reddit Scraper API

A powerful, feature-rich FastAPI application for scraping Reddit subreddits and posts with an easy-to-use RESTful interface.

## Overview

This project provides a robust API for extracting data from Reddit subreddits. It uses a background task system to handle scraping operations asynchronously, allowing users to start scraping tasks and check their status later.

## Features

- **Asynchronous scraping** with background tasks
- **Multiple output formats** (CSV, JSON, TXT)
- **Flexible sorting options** (hot, new, top, rising)
- **Time filtering** for top posts (hour, day, week, month, year, all)
- **Comment extraction** with configurable depth
- **Rate limiting** with configurable delays
- **Analytics generation** for scraped data
- **User-agent rotation** to avoid blocking
- **Comprehensive logging**
- **REST API** with full documentation

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/codersaadi/reddit-scraper-api.git
   cd reddit-scraper-api
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create necessary directories(optional):
   ```bash
   mkdir -p output logs
   ```

## Usage

### Starting the API Server

Run the following command to start the API server:

```bash
python main.py
```

This will start the server at `http://0.0.0.0:8000`. 

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/scrape` | POST | Start a new scraping task |
| `/tasks` | GET | Get all tasks |
| `/tasks/{task_id}` | GET | Get task status |
| `/download/{task_id}` | GET | Download task results |
| `/tasks/{task_id}` | DELETE | Delete a task |
| `/` | GET | API information |

### Examples

#### Starting a New Scrape Task

```bash
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "subreddit": "python",
    "post_limit": 50,
    "output_format": "json",
    "include_comments": true,
    "pages": 2,
    "sort_by": "hot",
    "time_filter": "all",
    "delay_min": 1.0,
    "delay_max": 3.0
  }'
```

Response:
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "subreddit": "python",
  "message": "Scraping task started"
}
```

#### Checking Task Status

```bash
curl -X GET "http://localhost:8000/tasks/3fa85f64-5717-4562-b3fc-2c963f66afa6"
```

Response:
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "completed",
  "subreddit": "python",
  "start_time": "2025-03-19T12:34:56.789Z",
  "completion_time": "2025-03-19T12:35:42.123Z",
  "post_count": 50,
  "output_file": "python_hot_3fa85f64-5717-4562-b3fc-2c963f66afa6_20250319_123456.json"
}
```

#### Downloading Results

```bash
curl -X GET "http://localhost:8000/tasks/3fa85f64-5717-4562-b3fc-2c963f66afa6/download" --output reddit_data.json
```

## Configuration Options

### Scrape Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subreddit` | string | (required) | Name of the subreddit to scrape |
| `post_limit` | integer | 25 | Maximum number of posts to scrape (1-100) |
| `output_format` | string | "json" | Format to save data ("csv", "json", "txt") |
| `include_comments` | boolean | false | Whether to scrape comments |
| `pages` | integer | 1 | Number of pages to scrape (1-10) |
| `sort_by` | string | "hot" | How to sort posts ("hot", "new", "top", "rising") |
| `time_filter` | string | "all" | Time filter for top posts ("hour", "day", "week", "month", "year", "all") |
| `delay_min` | number | 1.0 | Minimum delay between requests (seconds) |
| `delay_max` | number | 3.0 | Maximum delay between requests (seconds) |

## Technical Details

### Architecture

The application is built using:
- **FastAPI**: For the web API framework
- **BeautifulSoup**: For HTML parsing
- **Requests**: For HTTP requests
- **Pandas**: For data manipulation and analysis
- **Pydantic**: For data validation

### Background Tasks

Scraping operations run as background tasks to avoid blocking the API. Each task is assigned a unique ID that can be used to check its status and download results when complete.

### Data Storage

- Scraped data is stored in the `output` directory
- Logs are stored in the `logs` directory
- Task metadata is stored in memory (will be lost on server restart)

## Ethical Considerations

This tool is designed for legitimate research and data analysis purposes. When using this scraper:

- Be respectful of Reddit's servers by using appropriate delays between requests
- Comply with Reddit's Terms of Service and robots.txt
- Do not use the scraper for content that violates copyright or privacy laws
- Consider the privacy implications of collecting and storing user data

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
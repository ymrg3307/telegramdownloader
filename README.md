# Telegram Video/File Downloader

A simple application to download multiple videos and files from a Telegram channel.

## Prerequisites

- Python 3.7 or higher
- Telegram API credentials (API ID and API Hash)

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with your Telegram API credentials:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   ```

## How to get Telegram API credentials

1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Click on "API development tools"
4. Create a new application
5. Copy the API ID and API Hash

## Usage

Run the application:
```
python downloader.py
```

Follow the prompts to:
1. Enter the Telegram channel username or URL
2. Select the types of files to download (videos, documents, etc.)
3. Set the download location
4. Start downloading

## Features

- Download multiple files simultaneously
- Filter by file type
- Resume interrupted downloads
- Show download progress

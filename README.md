# Telegram Video/File Downloader

A powerful application to download multiple videos and files from Telegram channels, groups, and chats. This tool supports various URL formats and provides both command-line and graphical user interfaces.

## Features

- **Multiple Interface Options**: Command-line, GUI, and direct download script
- **Smart URL Handling**: Support for various URL formats including:
  - Channel usernames (e.g., `channelname`)
  - Channel IDs (e.g., `-2570734937`)
  - t.me links (e.g., `https://t.me/channelname`)
  - Web client URLs (e.g., `https://web.telegram.org/k/#-2570734937`)
- **Flexible File Filtering**: Download specific file types (videos, photos, documents, etc.)
- **Progress Tracking**: Real-time download progress with progress bars
- **Batch Processing**: Download multiple files in one go
- **Customizable Download Location**: Choose where to save your files
- **Detailed Logging**: Comprehensive logs for troubleshooting

## Prerequisites

- Python 3.7 or higher
- Telegram API credentials (API ID and API Hash)

## Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd telegramvideodownloader
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with your Telegram API credentials:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   ```
   You can copy the `.env.example` file and fill in your details.

## How to get Telegram API credentials

1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Click on "API development tools"
4. Create a new application
5. Copy the API ID and API Hash

## Usage

### Command-line Version

Run the command-line version with:

```bash
python downloader.py
```

Follow the prompts to:
1. Enter the Telegram channel username or URL
2. Specify which file types to download (videos, photos, documents, etc.)
3. Set the download location
4. Limit the number of messages to scan (optional)

### GUI Version (Recommended)

Run the GUI version with:

```bash
python gui_downloader.py
```

The graphical interface will:
1. Allow you to enter your API credentials (or load them from .env)
2. Let you browse for a download folder
3. Enter channel details and file type filters
4. Show download progress with a progress bar
5. Display logs of the download process

### Direct Download Script

For automated or scripted downloads:

```bash
python direct_download.py [channel] --types [file_types] --folder [download_folder] --limit [message_limit]
```

Example:
```bash
python direct_download.py -2570734937 --types video,photo --folder my_downloads --limit 100
```

## Troubleshooting

### Channel Access Issues

If you encounter problems accessing a channel:

1. Make sure you're a member of the channel/group you're trying to download from
2. Try using different channel identifier formats (username, ID, or URL)
3. Check the logs for detailed error messages

### File Type Filtering

When filtering by file type:

- For videos, use `video` as the file type
- For photos, use `photo`
- For documents, you can specify the extension (e.g., `pdf`, `doc`, `mp3`)
- Leave empty to download all file types

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

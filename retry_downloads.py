#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import dotenv
from telethon import TelegramClient

# Import the downloader module
from downloader import TelegramDownloader

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Changed from INFO to WARNING to reduce logs
)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("Error: API_ID and API_HASH must be set in the .env file")
    print("Please follow the instructions in the README.md to obtain these credentials")
    sys.exit(1)

async def retry_failed_downloads():
    """Standalone function to retry failed downloads from a previous session"""
    # Create downloader instance
    downloader = TelegramDownloader(API_ID, API_HASH)
    
    # Connect to Telegram
    await downloader.connect()
    
    print("Telegram Download Retry Tool")
    
    # Get channel input
    channel_input = input("\nEnter the same Telegram channel username or URL as before: ")
    
    # Process the channel input
    from downloader import extract_channel_info
    processed_channel_input = extract_channel_info(channel_input)
    
    # Get file types to filter
    print("\nSelect file types to download (comma-separated, leave empty for all):")
    print("Note: Make sure to use the same file types as in your original download")
    file_types_input = input("File types: ")
    
    if file_types_input.strip():
        file_types = [ft.strip().lower() for ft in file_types_input.split(',')]
        downloader.set_file_types(file_types)
    
    # Get download folder
    download_folder = input("\nEnter download folder (default: downloads): ")
    if download_folder.strip():
        downloader.set_download_folder(download_folder)
    
    # Get message limit (should be higher than original to ensure all failed files are included)
    limit_input = input("\nEnter maximum number of messages to scan (should be at least as large as original scan): ")
    limit = int(limit_input) if limit_input.strip() else None
    
    # Get batch size
    batch_size_input = input("\nEnter batch size for concurrent downloads (default: 10): ")
    batch_size = int(batch_size_input) if batch_size_input.strip() else 10
    
    # Get max retries
    max_retries_input = input("\nEnter maximum number of retry attempts per file (default: 3): ")
    max_retries = int(max_retries_input) if max_retries_input.strip() else 3
    
    # Get list of all downloaded files to skip them
    download_dir = Path(downloader.download_folder)
    existing_files = set()
    if download_dir.exists():
        for file_path in download_dir.glob("*"):
            if file_path.is_file():
                existing_files.add(file_path.name)
    
    print(f"Found {len(existing_files)} existing files that will be skipped")
    
    # Create a custom download function that skips existing files
    original_download_file = downloader.download_file
    
    async def download_file_if_not_exists(message):
        """Wrapper to skip already downloaded files"""
        # Generate the filename that would be used
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        msg_id = message.id
        
        # Check if this message was already downloaded by checking ID in filename
        for existing_file in existing_files:
            if f"_{msg_id}_" in existing_file or f"_{msg_id}." in existing_file:
                print(f"Skipping message ID {msg_id} - already downloaded as {existing_file}")
                return True
        
        # If not found in existing files, download it
        return await original_download_file(message)
    
    # Replace the download method temporarily
    downloader.download_file = download_file_if_not_exists
    
    # Start the download process
    print("Starting retry download process...")
    await downloader.download_from_channel(processed_channel_input, limit, batch_size)
    
    # If there are still failed downloads, offer to retry them
    if downloader.failed_count > 0:
        retry_input = input(f"\n{downloader.failed_count} files failed to download. Do you want to retry these specific files? (y/n): ")
        if retry_input.lower() in ['y', 'yes']:
            await downloader.retry_failed_downloads(max_retries)
    
    # Disconnect
    await downloader.client.disconnect()
    
    print("\nRetry process completed!")

if __name__ == "__main__":
    asyncio.run(retry_failed_downloads())

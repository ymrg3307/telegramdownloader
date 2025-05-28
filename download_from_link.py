#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
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

async def download_from_telegram_link():
    """Download a video or file from a Telegram message link"""
    # Create downloader instance
    downloader = TelegramDownloader(API_ID, API_HASH)
    
    # Connect to Telegram
    await downloader.connect()
    
    print("Telegram Link Downloader")
    
    # Get message link
    message_link = input("Enter Telegram message link: ")
    
    # Get download folder
    download_folder = input("\nEnter download folder (default: downloads): ")
    if download_folder.strip():
        downloader.set_download_folder(download_folder)
    
    # Download the file
    print("Downloading...")
    success = await downloader.download_from_link(message_link)
    
    # Summary
    if success:
        print("Download completed successfully!")
    else:
        print("Download failed. Please check the link and try again.")
    
    # Disconnect
    await downloader.client.disconnect()

def main():
    """Main function to handle command line arguments"""
    # Check if a link was provided as a command line argument
    if len(sys.argv) > 1:
        asyncio.run(download_with_link(sys.argv[1]))
    else:
        asyncio.run(download_from_telegram_link())

async def download_with_link(link):
    """Download using a link provided as command line argument"""
    downloader = TelegramDownloader(API_ID, API_HASH)
    await downloader.connect()
    success = await downloader.download_from_link(link)
    if success:
        print("Download completed successfully!")
    else:
        print("Download failed. Please check the link and try again.")
    await downloader.client.disconnect()

if __name__ == "__main__":
    main()

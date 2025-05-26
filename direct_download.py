#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
from downloader import TelegramDownloader, extract_channel_info

# Load environment variables
import dotenv
dotenv.load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("Error: API_ID and API_HASH must be set in the .env file")
    print("Please follow the instructions in the README.md to obtain these credentials")
    sys.exit(1)

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download files from a Telegram channel')
    parser.add_argument('channel', help='Telegram channel username, URL, or ID')
    parser.add_argument('--types', help='File types to download (comma-separated, e.g., video,photo,pdf)')
    parser.add_argument('--folder', default='downloads', help='Download folder (default: downloads)')
    parser.add_argument('--limit', type=int, help='Maximum number of messages to scan')
    
    args = parser.parse_args()
    
    # Process the channel input
    channel_input = extract_channel_info(args.channel)
    print(f"Processed channel input: {channel_input}")
    
    # Create the downloader
    downloader = TelegramDownloader(API_ID, API_HASH, args.folder)
    
    # Connect to Telegram
    await downloader.connect()
    
    # Set file types if specified
    if args.types:
        file_types = [ft.strip().lower() for ft in args.types.split(',')]
        downloader.set_file_types(file_types)
        print(f"Filtering for file types: {', '.join(file_types)}")
    
    # Download files
    print(f"\nStarting download from {args.channel} to folder {args.folder}...")
    await downloader.download_from_channel(channel_input, args.limit)

if __name__ == "__main__":
    asyncio.run(main())

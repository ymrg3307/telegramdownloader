#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import dotenv
from telethon import TelegramClient

# Import the downloader module
from downloader import TelegramDownloader

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
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

class BatchLinkDownloader:
    def __init__(self, api_id: str, api_hash: str, download_folder: str = "downloads"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.download_folder = download_folder
        self.downloader = TelegramDownloader(api_id, api_hash, download_folder)
        
        # Track successful and failed downloads
        self.successful_links = []
        self.failed_links = []
        self.pending_links = []
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)
        
    async def connect(self):
        """Connect to Telegram"""
        await self.downloader.connect()
        
    async def download_from_links_file(self, links_file: str, batch_size: int = 5, media_types: List[str] = None):
        """Download files from a list of links in a file, processing in batches"""
        # Read links from file
        try:
            with open(links_file, 'r') as f:
                links = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading links file: {e}")
            return
        
        # Set file types if specified
        if media_types:
            self.downloader.set_file_types(media_types)
            print(f"Will download files of types: {', '.join(media_types)}")
        
        # Initialize pending links
        self.pending_links = links.copy()
        total_links = len(links)
        
        print(f"Found {total_links} links in {links_file}")
        print(f"Will process in batches of {batch_size}")
        
        # Process links in batches
        batch_num = 0
        while self.pending_links:
            batch_num += 1
            current_batch = self.pending_links[:batch_size]
            self.pending_links = self.pending_links[batch_size:]
            
            print(f"\nProcessing batch {batch_num} ({len(current_batch)} links)")
            
            # Process each link in the batch concurrently
            tasks = [self.process_link(link) for link in current_batch]
            await asyncio.gather(*tasks)
            
            # Progress update
            completed = len(self.successful_links) + len(self.failed_links)
            progress_percent = (completed / total_links) * 100
            print(f"Overall progress: {progress_percent:.1f}% ({completed}/{total_links})")
            print(f"Successful: {len(self.successful_links)}, Failed: {len(self.failed_links)}")
            
            # Ask if user wants to continue after each batch
            if self.pending_links and batch_num % 3 == 0:  # Ask every 3 batches
                continue_input = input("Continue to next batch? (y/n, default: y): ")
                if continue_input.lower() in ['n', 'no']:
                    print("Download process paused by user")
                    break
        
        # Final report
        print("\nDownload summary:")
        print(f"Total links: {total_links}")
        print(f"Successfully downloaded: {len(self.successful_links)}")
        print(f"Failed downloads: {len(self.failed_links)}")
        
        # Save failed links to file for retry
        if self.failed_links:
            self._save_failed_links()
    
    async def process_link(self, link: str) -> bool:
        """Process a single link and track its success/failure"""
        try:
            print(f"Downloading from: {link}")
            success = await self.downloader.download_from_link(link)
            
            if success:
                self.successful_links.append(link)
                return True
            else:
                self.failed_links.append(link)
                return False
        except Exception as e:
            logger.error(f"Error processing link {link}: {e}")
            self.failed_links.append(link)
            return False
    
    def _save_failed_links(self):
        """Save failed links to a file for later retry"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_file = f"failed_links_{timestamp}.txt"
        
        with open(failed_file, 'w') as f:
            for link in self.failed_links:
                f.write(f"{link}\n")
        
        print(f"Failed links saved to {failed_file}")
        print("You can retry these links later using this script")
    
    async def retry_failed_links(self, failed_links_file: str, batch_size: int = 5):
        """Retry downloading from a file of failed links"""
        # Reset tracking lists
        self.successful_links = []
        self.failed_links = []
        
        # Read failed links
        try:
            with open(failed_links_file, 'r') as f:
                self.pending_links = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading failed links file: {e}")
            return
        
        print(f"Retrying {len(self.pending_links)} failed links from {failed_links_file}")
        
        # Process in batches
        await self.download_from_links_file(failed_links_file, batch_size)

async def main():
    # Create downloader instance
    batch_downloader = BatchLinkDownloader(API_ID, API_HASH)
    
    # Connect to Telegram
    await batch_downloader.connect()
    
    # Check if we're retrying failed links
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and "failed_links" in sys.argv[1]:
        # Retry mode
        failed_links_file = sys.argv[1]
        print(f"Retry mode: Will retry links from {failed_links_file}")
        
        batch_size_input = input("Enter batch size for retry (default: 3): ")
        batch_size = int(batch_size_input) if batch_size_input.strip() else 3
        
        await batch_downloader.retry_failed_links(failed_links_file, batch_size)
    else:
        # Normal mode
        links_file = input("Enter the path to the links file: ") if len(sys.argv) <= 1 else sys.argv[1]
        
        if not os.path.exists(links_file):
            print(f"Error: File {links_file} not found")
            return
        
        # Get media types to filter (optional)
        media_types_input = input("Enter media types to download (comma-separated, leave empty for all): ")
        media_types = [mt.strip() for mt in media_types_input.split(',') if mt.strip()]
        
        # Get batch size
        batch_size_input = input("Enter batch size (default: 5): ")
        batch_size = int(batch_size_input) if batch_size_input.strip() else 5
        
        # Get download folder
        download_folder = input("Enter download folder (default: downloads): ")
        if download_folder.strip():
            batch_downloader.download_folder = download_folder
            batch_downloader.downloader.set_download_folder(download_folder)
        
        # Start downloading
        await batch_downloader.download_from_links_file(links_file, batch_size, media_types)
    
    # Disconnect
    await batch_downloader.downloader.client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

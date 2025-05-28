#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Union

import dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Document, MessageMediaDocument, MessageMediaPhoto, Photo
from telethon.tl.types import InputChannel, Channel, Chat, User, Message
from tqdm import tqdm

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

class TelegramDownloader:
    def __init__(self, api_id: str, api_hash: str, download_folder: str = "downloads"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.download_folder = download_folder
        self.client = TelegramClient('telegram_downloader_session', api_id, api_hash)
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)
        
        # Set of file types to download
        self.file_types: Set[str] = set()
        
        # Download counter
        self.downloaded_count = 0
        self.failed_count = 0
        
        # Track failed downloads for retry
        self.failed_messages = []
        
    async def connect(self):
        """Connect to Telegram"""
        await self.client.start()
        if not await self.client.is_user_authorized():
            print("You need to log in to your Telegram account.")
            await self.client.send_code_request(input("Enter your phone number: "))
            await self.client.sign_in(input("Enter your phone number again: "), input("Enter the code you received: "))
        
        print(f"Logged in as {(await self.client.get_me()).first_name}")
    
    async def get_entity(self, channel_input: str) -> Union[Channel, Chat, User, None]:
        """Get the entity (channel, chat, user) from the input"""
        try:
            # Handle web client URLs (e.g., https://web.telegram.org/k/#-1234567890)
            if 'web.telegram.org' in channel_input and '#' in channel_input:
                # Extract the channel ID from the URL
                channel_id_str = channel_input.split('#')[-1]
                
                # If it starts with a dash, it's likely a channel ID
                if channel_id_str.startswith('-'):
                    try:
                        # Convert to integer (Telegram channel IDs are integers)
                        channel_id = int(channel_id_str)
                        print(f"Trying to access channel with ID: {channel_id}")
                    except ValueError:
                        print(f"Could not parse channel ID from {channel_id_str}")
                        channel_id = None
                        
                    if channel_id:
                        # For supergroups/channels, we need to use PeerChannel with the correct ID format
                        # Channel IDs in Telegram's API are the regular ID with -100 prefix
                        # If it already starts with -100, use it as is
                        if str(channel_id).startswith('-100'):
                            peer_id = int(str(channel_id)[4:])  # Remove the -100 prefix
                        else:
                            # If it starts with just a dash, it might be a regular channel ID
                            # We need to convert it to a proper channel ID format
                            if str(channel_id).startswith('-'):
                                peer_id = int(str(channel_id)[1:])  # Remove the dash
                            else:
                                peer_id = channel_id
                                
                        try:
                            from telethon.tl.types import PeerChannel, InputPeerChannel
                            # Try different approaches to get the entity
                            try:
                                # Try with PeerChannel
                                return await self.client.get_entity(PeerChannel(peer_id))
                            except Exception as e1:
                                print(f"PeerChannel approach failed: {e1}")
                                try:
                                    # Try with InputPeerChannel
                                    return await self.client.get_entity(InputPeerChannel(peer_id, 0))
                                except Exception as e2:
                                    print(f"InputPeerChannel approach failed: {e2}")
                                    # Try with -100 prefix format
                                    channel_100_id = -1000000000000 - peer_id
                                    return await self.client.get_entity(channel_100_id)
                        except Exception as e:
                            print(f"All channel ID approaches failed: {e}")
            
            # Handle t.me links
            if '/' in channel_input:
                if 't.me/' in channel_input:
                    channel_input = channel_input.split('t.me/')[1]
                elif 'telegram.me/' in channel_input:
                    channel_input = channel_input.split('telegram.me/')[1]
                elif 'telegram.dog/' in channel_input:
                    channel_input = channel_input.split('telegram.dog/')[1]
                
                # Remove trailing slashes and any parameters
                channel_input = channel_input.split('?')[0].rstrip('/')
            
            # Check if it's a pure channel ID (number)
            if channel_input.lstrip('-').isdigit():
                channel_id = int(channel_input)
                
                # For supergroups/channels, we need to use the correct ID format
                if str(channel_id).startswith('-100'):
                    # Already in the right format
                    pass
                elif str(channel_id).startswith('-'):
                    # Convert to -100 format for channels/supergroups
                    try:
                        from telethon.tl.types import PeerChannel
                        peer_id = int(str(channel_id)[1:])  # Remove the dash
                        return await self.client.get_entity(PeerChannel(peer_id))
                    except Exception as e:
                        print(f"PeerChannel approach failed: {e}")
                        # Try with -100 prefix format
                        channel_id = int(f"-100{str(channel_id)[1:]}")
                
                # Try to get entity with the channel ID
                try:
                    return await self.client.get_entity(channel_id)
                except Exception as e:
                    print(f"Error getting entity with ID {channel_id}: {e}")
            
            # Try to get the entity by username or other identifiers
            print(f"Trying to access channel with identifier: {channel_input}")
            entity = await self.client.get_entity(channel_input)
            return entity
        except Exception as e:
            logger.error(f"Error getting entity: {e}")
            return None
    
    async def get_messages(self, entity, limit: Optional[int] = None) -> List[Message]:
        """Get messages from the entity"""
        messages = []
        try:
            async for message in self.client.iter_messages(entity, limit=limit):
                messages.append(message)
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
        
        return messages
    
    async def download_file(self, message: Message) -> bool:
        """Download a file from a message"""
        try:
            if message.media:
                # Determine file type and mime type
                file_type = None
                mime_type = None
                file_name = None
                
                # Minimal info
                if isinstance(message.media, MessageMediaDocument):
                    doc = message.media.document
                    mime_type = doc.mime_type
                    
                    # Check if it's a video based on mime type
                    if mime_type.startswith('video/'):
                        file_type = 'video'
                    
                    # Try to get file name and extension from attributes
                    for attr in doc.attributes:
                        if hasattr(attr, 'file_name') and attr.file_name:
                            file_name = attr.file_name
                            file_ext = os.path.splitext(file_name)[1].lower()[1:]
                            if not file_type:  # Only set if not already determined by mime type
                                file_type = file_ext
                            break
                    
                    # If no file name found but we have mime type, use that to determine extension
                    if not file_name and mime_type:
                        ext = mime_type.split('/')[1] if '/' in mime_type else 'unknown'
                        file_type = ext
                        # Using mime type to determine extension
                
                elif isinstance(message.media, MessageMediaPhoto):
                    file_type = "photo"
                
                # Simplified output
                if self.file_types:
                    print(f"File type: {file_type}, Requested types: {', '.join(self.file_types)}")
                
                # Check if we want to download this file type
                should_download = False
                if not self.file_types:  # Download all types if no filter
                    should_download = True
                elif file_type:
                    # Check if the file type matches any of the requested types
                    if file_type in self.file_types:
                        should_download = True
                    # Special case for video: check mime type as well
                    elif 'video' in self.file_types and mime_type and mime_type.startswith('video/'):
                        should_download = True
                
                if should_download:
                    # Generate a unique filename
                    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    msg_id = message.id
                    
                    # Determine file extension and name
                    if hasattr(message.media, 'document'):
                        if file_name:  # Use the file name we found earlier
                            file_name = f"{date_str}_{msg_id}_{file_name}"
                        else:
                            # Determine extension from mime type
                            mime_type = message.media.document.mime_type
                            ext = mime_type.split('/')[1] if '/' in mime_type else 'unknown'
                            file_name = f"{date_str}_{msg_id}.{ext}"
                    else:
                        # For photos
                        file_name = f"{date_str}_{msg_id}.jpg"
                    
                    # Full path for the file
                    file_path = os.path.join(self.download_folder, file_name)
                    
                    # Download the file with progress bar
                    print(f"Downloading: {file_name}")
                    
                    # Get file size for progress bar
                    file_size = getattr(message.media.document, 'size', 0) if hasattr(message.media, 'document') else 0
                    
                    # Create progress bar
                    progress_bar = tqdm(total=file_size, unit='B', unit_scale=True, desc=file_name)
                    
                    # Custom progress callback
                    async def progress_callback(current, total):
                        progress_bar.update(current - progress_bar.n)
                    
                    # Download the file
                    await self.client.download_media(
                        message,
                        file_path,
                        progress_callback=progress_callback if file_size else None
                    )
                    
                    # Close progress bar
                    progress_bar.close()
                    
                    print(f"Downloaded: {file_name}")
                    self.downloaded_count += 1
                    return True
                else:
                    print(f"Skipping file because it doesn't match the requested types")
            else:
                print(f"Message {message.id} has no media")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            print(f"Error downloading file: {e}")
            self.failed_count += 1
            # Track failed message for retry
            self.failed_messages.append(message)
        
        return False
    
    async def download_from_channel(self, channel_input: str, limit: Optional[int] = None, batch_size: int = 10):
        """Download files from a channel in batches"""
        entity = await self.get_entity(channel_input)
        if not entity:
            print(f"Could not find channel: {channel_input}")
            return
        
        print(f"Downloading from: {getattr(entity, 'title', getattr(entity, 'username', channel_input))}")
        
        messages = await self.get_messages(entity, limit)
        print(f"Found {len(messages)} messages")
        
        # Filter messages with media
        media_messages = [msg for msg in messages if msg.media]
        print(f"Found {len(media_messages)} messages with media")
        
        # Process files in batches
        total_batches = (len(media_messages) + batch_size - 1) // batch_size  # Ceiling division
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(media_messages))
            batch = media_messages[start_idx:end_idx]
            
            print(f"\nProcessing batch {batch_num + 1}/{total_batches} (files {start_idx + 1}-{end_idx})")
            
            # Process batch concurrently
            download_tasks = [self.download_file(message) for message in batch]
            await asyncio.gather(*download_tasks)
            
            # Print batch summary
            print(f"Batch {batch_num + 1} complete: {end_idx - start_idx} files processed")
        
        print(f"\nDownload summary:")
        print(f"Successfully downloaded: {self.downloaded_count} files")
        print(f"Failed downloads: {self.failed_count} files")
        
        # Offer retry if there are failed downloads
        if self.failed_messages:
            print(f"\n{len(self.failed_messages)} files failed to download. You can retry them later using the retry_failed_downloads method.")
    
    def set_file_types(self, file_types: List[str]):
        """Set the file types to download"""
        self.file_types = set(file_types)
    
    def set_download_folder(self, folder: str):
        """Set the download folder"""
        self.download_folder = folder
        os.makedirs(self.download_folder, exist_ok=True)
    
    async def download_from_link(self, message_link: str):
        """Download a video or file from a Telegram message link
        
        Args:
            message_link: A Telegram message link like https://t.me/channel_name/123
                          or private channel format https://t.me/c/channel_id/message_id
        
        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            # Parse the link to extract channel name/id and message ID
            if not ('t.me/' in message_link or 'telegram.me/' in message_link):
                print(f"Invalid Telegram link format: {message_link}")
                print("Link should be in format: https://t.me/channel_name/123 or https://t.me/c/channel_id/message_id")
                return False
            
            # Extract channel information and message ID
            parts = message_link.split('/')
            if len(parts) < 5:  # Need at least protocol://domain/channel/message_id
                print(f"Invalid link format: {message_link}")
                return False
            
            # Handle different link formats
            is_private_channel = False
            channel_identifier = None
            message_id = None
            
            # Find the t.me or telegram.me part
            for i, part in enumerate(parts):
                if part in ['t.me', 'telegram.me'] and i+1 < len(parts):
                    # Check if it's a private channel format (t.me/c/channel_id/message_id)
                    if parts[i+1] == 'c' and i+2 < len(parts) and i+3 < len(parts):
                        is_private_channel = True
                        channel_identifier = parts[i+2]  # This is the channel ID
                        if parts[i+3].isdigit():
                            message_id = int(parts[i+3])
                    else:
                        # Regular format (t.me/channel_name/message_id)
                        channel_identifier = parts[i+1]  # This is the channel name
                        if i+2 < len(parts) and parts[i+2].isdigit():
                            message_id = int(parts[i+2])
                    break
            
            if not channel_identifier or not message_id:
                print(f"Could not extract channel information and message ID from link: {message_link}")
                return False
            
            # For private channels, we need to format the channel ID correctly
            entity = None
            if is_private_channel:
                print(f"Accessing private channel...")
                # Try to convert channel_identifier to an integer and format it correctly
                try:
                    channel_id = int(channel_identifier)
                    # For private channels, we need to use the -100 prefix format
                    if not str(channel_id).startswith('-100'):
                        channel_id = -1000000000000 - channel_id
                    entity = await self.client.get_entity(channel_id)
                except Exception:
                    # Try alternative approach with PeerChannel
                    try:
                        from telethon.tl.types import PeerChannel
                        peer_id = int(channel_identifier)
                        entity = await self.client.get_entity(PeerChannel(peer_id))
                    except Exception:
                        pass
            else:
                print(f"Accessing channel...")
                entity = await self.get_entity(channel_identifier)
            
            if not entity:
                print(f"Could not find channel with identifier: {channel_identifier}")
                return False
            
            # Get the specific message
            message = await self.client.get_messages(entity, ids=message_id)
            if not message:
                print(f"Could not find message with ID {message_id}")
                return False
            
            # Download the file
            print(f"Found message. Downloading...")
            result = await self.download_file(message)
            
            if result:
                print(f"Successfully downloaded file from {message_link}")
            else:
                print(f"Failed to download file from {message_link}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading from link: {e}")
            print(f"Error downloading from link: {e}")
            return False
        
    async def retry_failed_downloads(self, max_retries: int = 3):
        """Retry downloading files that failed previously"""
        if not self.failed_messages:
            print("No failed downloads to retry.")
            return
            
        print(f"Retrying {len(self.failed_messages)} failed downloads...")
        
        # Make a copy of the failed messages list
        messages_to_retry = self.failed_messages.copy()
        self.failed_messages = []  # Clear the list for this retry attempt
        
        # Reset failed count for this retry session
        previous_failed_count = self.failed_count
        self.failed_count = 0
        
        # Retry each failed download with multiple attempts
        for attempt in range(1, max_retries + 1):
            if not messages_to_retry:
                break
                
            print(f"\nRetry attempt {attempt}/{max_retries}")
            
            # Try to download each failed file
            retry_tasks = [self.download_file(message) for message in messages_to_retry]
            results = await asyncio.gather(*retry_tasks)
            
            # Filter out successful downloads
            still_failed = [msg for msg, success in zip(messages_to_retry, results) if not success]
            
            # Update counters
            successful_retries = len(messages_to_retry) - len(still_failed)
            print(f"Successfully downloaded {successful_retries} files in retry attempt {attempt}")
            
            # If all files were downloaded or we've reached max retries, break
            if not still_failed:
                print("All files successfully downloaded!")
                break
            
            # Update the list for next retry attempt
            messages_to_retry = still_failed
            
            if attempt < max_retries:
                print(f"{len(still_failed)} files still failed. Trying again...")
                # Small delay between retry attempts
                await asyncio.sleep(2)
        
        # Final report
        print(f"\nRetry summary:")
        print(f"Previously failed: {previous_failed_count} files")
        print(f"Successfully retried: {previous_failed_count - self.failed_count} files")
        print(f"Still failed: {self.failed_count} files")

def extract_channel_info(channel_input: str) -> str:
    """Helper function to extract channel information from various URL formats"""
    # Handle web client URLs (e.g., https://web.telegram.org/k/#-1234567890)
    if 'web.telegram.org' in channel_input:
        if '#' in channel_input:
            # Extract the channel ID from the URL
            channel_id_str = channel_input.split('#')[-1]
            print(f"Extracted channel ID from web URL: {channel_id_str}")
            return channel_id_str
        elif '?p=' in channel_input:
            # Some web client URLs use ?p= format
            channel_id_str = channel_input.split('?p=')[-1].split('&')[0]
            print(f"Extracted channel ID from web URL query param: {channel_id_str}")
            return channel_id_str
    
    # Handle t.me links
    if '/' in channel_input:
        if 't.me/' in channel_input:
            channel_input = channel_input.split('t.me/')[1]
        elif 'telegram.me/' in channel_input:
            channel_input = channel_input.split('telegram.me/')[1]
        elif 'telegram.dog/' in channel_input:
            channel_input = channel_input.split('telegram.dog/')[1]
        
        # Remove trailing slashes and any parameters
        channel_input = channel_input.split('?')[0].rstrip('/')
    
    return channel_input

async def main():
    # Create downloader instance
    downloader = TelegramDownloader(API_ID, API_HASH)
    
    # Connect to Telegram
    await downloader.connect()
    
    # Get channel input
    channel_input = input("\nEnter Telegram channel username or URL: ")
    
    # Process the channel input to handle various URL formats
    processed_channel_input = extract_channel_info(channel_input)
    print(f"Processed channel input: {processed_channel_input}")
    
    # Get file types
    print("\nSelect file types to download (comma-separated, leave empty for all):")
    print("Examples: video, photo, pdf, doc, mp3, etc.")
    file_types_input = input("File types: ")
    
    if file_types_input.strip():
        file_types = [ft.strip().lower() for ft in file_types_input.split(',')]
        downloader.set_file_types(file_types)
        print(f"Will download files of types: {', '.join(file_types)}")
    else:
        print("Will download all file types")
    
    # Get download folder
    download_folder = input("\nEnter download folder (default: downloads): ")
    if download_folder.strip():
        downloader.set_download_folder(download_folder)
    
    # Get message limit
    limit_input = input("\nEnter maximum number of messages to scan (default: all): ")
    limit = int(limit_input) if limit_input.strip() else None
    
    # Get batch size
    batch_size_input = input("\nEnter batch size for concurrent downloads (default: 10): ")
    batch_size = int(batch_size_input) if batch_size_input.strip() else 10
    
    # Download files
    print("\nStarting download...")
    await downloader.download_from_channel(processed_channel_input, limit, batch_size)
    
    # Ask if user wants to retry failed downloads
    if downloader.failed_count > 0:
        retry_input = input(f"\n{downloader.failed_count} files failed to download. Do you want to retry? (y/n): ")
        if retry_input.lower() in ['y', 'yes']:
            max_retries_input = input("Enter maximum number of retry attempts (default: 3): ")
            max_retries = int(max_retries_input) if max_retries_input.strip() else 3
            await downloader.retry_failed_downloads(max_retries)
    
    # Disconnect
    await downloader.client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

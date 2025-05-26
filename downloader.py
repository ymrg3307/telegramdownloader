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
    level=logging.INFO
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
                
                # Debug info
                print(f"Message ID: {message.id}, Media type: {type(message.media).__name__}")
                
                if isinstance(message.media, MessageMediaDocument):
                    doc = message.media.document
                    mime_type = doc.mime_type
                    print(f"MIME type: {mime_type}")
                    
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
                            print(f"Found file name: {file_name}, extension: {file_ext}")
                            break
                    
                    # If no file name found but we have mime type, use that to determine extension
                    if not file_name and mime_type:
                        ext = mime_type.split('/')[1] if '/' in mime_type else 'unknown'
                        file_type = ext
                        print(f"No filename found, using mime type to determine extension: {ext}")
                
                elif isinstance(message.media, MessageMediaPhoto):
                    file_type = "photo"
                    print("Media is a photo")
                
                # Debug output for file type detection
                print(f"Detected file type: {file_type}")
                print(f"User requested file types: {self.file_types}")
                
                # Check if we want to download this file type
                should_download = False
                if not self.file_types:  # Download all types if no filter
                    should_download = True
                    print("No file type filter, downloading all types")
                elif file_type:
                    # Check if the file type matches any of the requested types
                    if file_type in self.file_types:
                        should_download = True
                        print(f"File type {file_type} matches requested type")
                    # Special case for video: check mime type as well
                    elif 'video' in self.file_types and mime_type and mime_type.startswith('video/'):
                        should_download = True
                        print(f"MIME type {mime_type} matches requested video type")
                    else:
                        print(f"File type {file_type} does not match any requested type")
                
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
        
        return False
    
    async def download_from_channel(self, channel_input: str, limit: Optional[int] = None):
        """Download files from a channel"""
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
        
        # Download files
        for message in media_messages:
            await self.download_file(message)
        
        print(f"\nDownload summary:")
        print(f"Successfully downloaded: {self.downloaded_count} files")
        print(f"Failed downloads: {self.failed_count} files")
    
    def set_file_types(self, file_types: List[str]):
        """Set the file types to download"""
        self.file_types = set(file_types)
    
    def set_download_folder(self, folder: str):
        """Set the download folder"""
        self.download_folder = folder
        os.makedirs(self.download_folder, exist_ok=True)

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
    # Create the downloader
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
    
    # Get download folder
    download_folder = input("\nEnter download folder (default: downloads): ")
    if download_folder.strip():
        downloader.set_download_folder(download_folder)
    
    # Get message limit
    limit_input = input("\nEnter maximum number of messages to scan (default: all): ")
    limit = int(limit_input) if limit_input.strip() else None
    
    # Download files
    print("\nStarting download...")
    await downloader.download_from_channel(processed_channel_input, limit)

if __name__ == "__main__":
    asyncio.run(main())

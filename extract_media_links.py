#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

import dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, Document

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

class MediaLinkExtractor:
    def __init__(self, api_id: str, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = TelegramClient('telegram_extractor_session', api_id, api_hash)
        self.media_types = []
        
    async def connect(self):
        """Connect to Telegram"""
        await self.client.start()
        if not await self.client.is_user_authorized():
            print("You need to log in to your Telegram account.")
            await self.client.send_code_request(input("Enter your phone number: "))
            await self.client.sign_in(input("Enter your phone number again: "), input("Enter the code you received: "))
        
        print(f"Logged in successfully")
    
    def set_media_types(self, media_types: List[str]):
        """Set the media types to extract (e.g., video, pdf)"""
        self.media_types = [media_type.lower() for media_type in media_types]
    
    async def extract_links_from_channel(self, channel_url: str, limit: int = None) -> List[Dict[str, Any]]:
        """Extract links to messages with specified media types from a channel"""
        # Parse the channel URL
        channel_id = self._extract_channel_id(channel_url)
        if not channel_id:
            print(f"Could not extract channel ID from URL: {channel_url}")
            return []
        
        print(f"Extracting media links from channel ID: {channel_id}")
        
        # Get the entity
        try:
            # For web client URLs with negative IDs, we need to format them correctly
            if str(channel_id).startswith('-'):
                if str(channel_id).startswith('-100'):
                    # Already in the right format
                    entity = await self.client.get_entity(int(channel_id))
                else:
                    # Convert to -100 format for channels/supergroups
                    formatted_id = int(f"-100{str(channel_id)[1:]}")
                    entity = await self.client.get_entity(formatted_id)
            else:
                entity = await self.client.get_entity(channel_id)
        except Exception as e:
            print(f"Error getting entity: {e}")
            return []
        
        # Get messages from the channel
        messages = []
        try:
            print("Fetching messages...")
            async for message in self.client.iter_messages(entity, limit=limit):
                messages.append(message)
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []
        
        print(f"Found {len(messages)} messages in the channel")
        
        # Filter messages with the specified media types
        media_links = []
        for message in messages:
            if message.media:
                media_type = self._get_media_type(message)
                
                # Check if the media type matches what we're looking for
                if not self.media_types or media_type in self.media_types:
                    # Create a direct link to this message
                    # For private channels, format should be https://t.me/c/channel_id/message_id
                    # where channel_id is without the -100 prefix
                    if str(channel_id).startswith('-100'):
                        # Remove the -100 prefix for the link
                        clean_channel_id = str(channel_id)[4:]
                        message_link = f"https://t.me/c/{clean_channel_id}/{message.id}"
                    elif str(channel_id).startswith('-'):
                        # For other private channels, we still need to format correctly
                        # The channel ID in the link should be without any prefix
                        clean_channel_id = str(channel_id)[1:]
                        message_link = f"https://t.me/c/{clean_channel_id}/{message.id}"
                    else:
                        # Public channels/users
                        message_link = f"https://t.me/{channel_id}/{message.id}"
                    
                    # Get file details
                    file_name = self._get_file_name(message)
                    file_size = self._get_file_size(message)
                    
                    media_links.append({
                        'link': message_link,
                        'type': media_type,
                        'message_id': message.id,
                        'date': message.date.strftime('%Y-%m-%d %H:%M:%S'),
                        'file_name': file_name,
                        'file_size': file_size
                    })
        
        print(f"Found {len(media_links)} messages with specified media types")
        return media_links
    
    def _extract_channel_id(self, channel_url: str) -> str:
        """Extract channel ID from various URL formats"""
        # Handle web client URLs (e.g., https://web.telegram.org/k/#-1234567890)
        if 'web.telegram.org' in channel_url and '#' in channel_url:
            # Extract the channel ID from the URL
            channel_id = channel_url.split('#')[-1]
            return channel_id
        
        # Handle t.me links
        if 't.me/' in channel_url:
            channel_name = channel_url.split('t.me/')[-1].split('/')[0]
            return channel_name
        
        # If it's just a channel ID
        if channel_url.lstrip('-').isdigit():
            return channel_url
        
        return channel_url
    
    def _get_media_type(self, message) -> str:
        """Get the media type of a message"""
        if not message.media:
            return 'text'
        
        if isinstance(message.media, MessageMediaPhoto):
            return 'photo'
        
        if isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            mime_type = doc.mime_type.lower()
            
            # Check for videos
            if mime_type.startswith('video/'):
                return 'video'
            
            # Check for PDFs
            if mime_type == 'application/pdf':
                return 'pdf'
            
            # Check for other document types
            if mime_type.startswith('audio/'):
                return 'audio'
            
            # Get extension from attributes if available
            for attr in doc.attributes:
                if hasattr(attr, 'file_name') and attr.file_name:
                    ext = os.path.splitext(attr.file_name)[1].lower()[1:]
                    if ext in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                        return 'document'
                    return ext
            
            # Default to the mime type's second part
            return mime_type.split('/')[1] if '/' in mime_type else 'document'
        
        return 'unknown'
    
    def _get_file_name(self, message) -> str:
        """Get the file name from a message"""
        if not message.media or not isinstance(message.media, MessageMediaDocument):
            return ""
        
        doc = message.media.document
        for attr in doc.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                return attr.file_name
        
        # If no filename, generate one based on mime type
        mime_type = doc.mime_type
        ext = mime_type.split('/')[1] if '/' in mime_type else 'bin'
        return f"file_{message.id}.{ext}"
    
    def _get_file_size(self, message) -> int:
        """Get the file size in bytes"""
        if not message.media:
            return 0
        
        if isinstance(message.media, MessageMediaDocument):
            return message.media.document.size
        
        return 0

async def main():
    # Create extractor instance
    extractor = MediaLinkExtractor(API_ID, API_HASH)
    
    # Connect to Telegram
    await extractor.connect()
    
    # Get channel URL
    channel_url = input("Enter Telegram channel URL: ")
    
    # Get media types to extract
    media_types_input = input("Enter media types to extract (comma-separated, e.g., video,pdf): ")
    media_types = [mt.strip() for mt in media_types_input.split(',') if mt.strip()]
    
    if media_types:
        extractor.set_media_types(media_types)
        print(f"Extracting links for media types: {', '.join(media_types)}")
    else:
        print("Extracting links for all media types")
    
    # Get message limit
    limit_input = input("Enter maximum number of messages to scan (leave empty for all): ")
    limit = int(limit_input) if limit_input.strip() else None
    
    # Extract links
    media_links = await extractor.extract_links_from_channel(channel_url, limit)
    
    # Display results
    if media_links:
        print("\nFound media links:")
        for i, link_info in enumerate(media_links, 1):
            file_size_str = f"{link_info['file_size'] / (1024*1024):.2f} MB" if link_info['file_size'] > 0 else "Unknown size"
            print(f"{i}. [{link_info['type']}] {link_info['file_name']} ({file_size_str})")
            print(f"   {link_info['link']}")
            print(f"   Date: {link_info['date']}")
            print()
        
        # Save links to file
        save_input = input("Save links to file? (y/n): ")
        if save_input.lower() in ['y', 'yes']:
            filename = f"media_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                for link_info in media_links:
                    f.write(f"{link_info['link']}\n")
            print(f"Links saved to {filename}")
    else:
        print("No media links found matching the criteria")
    
    # Disconnect
    await extractor.client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
import os
import sys
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Union

import dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
from telethon.tl.types import Channel, Chat, User, Message

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

class TelegramDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Channel Downloader")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Set application icon
        # self.root.iconbitmap("icon.ico")  # Uncomment and add icon if desired
        
        # Variables
        self.api_id = tk.StringVar(value=os.getenv('API_ID', ''))
        self.api_hash = tk.StringVar(value=os.getenv('API_HASH', ''))
        self.channel_input = tk.StringVar()
        self.download_folder = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        self.file_types = tk.StringVar()
        self.message_limit = tk.StringVar(value="100")
        self.is_downloading = False
        self.client = None
        
        # Create UI
        self.create_widgets()
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder.get(), exist_ok=True)
    
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API Credentials Frame
        cred_frame = ttk.LabelFrame(main_frame, text="Telegram API Credentials", padding="10")
        cred_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(cred_frame, text="API ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cred_frame, textvariable=self.api_id, width=30).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(cred_frame, text="API Hash:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cred_frame, textvariable=self.api_hash, width=50, show="*").grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Channel and Download Options Frame
        options_frame = ttk.LabelFrame(main_frame, text="Download Options", padding="10")
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(options_frame, text="Channel Username/URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(options_frame, textvariable=self.channel_input, width=50).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(options_frame, text="Download Folder:").grid(row=1, column=0, sticky=tk.W, pady=2)
        folder_frame = ttk.Frame(options_frame)
        folder_frame.grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Entry(folder_frame, textvariable=self.download_folder, width=40).pack(side=tk.LEFT)
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(options_frame, text="File Types (comma-separated):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(options_frame, textvariable=self.file_types, width=50).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(options_frame, text="Leave empty for all types. Examples: video, photo, pdf, doc, mp3").grid(row=3, column=1, sticky=tk.W)
        
        ttk.Label(options_frame, text="Message Limit:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(options_frame, textvariable=self.message_limit, width=10).grid(row=4, column=1, sticky=tk.W, pady=2)
        
        # Buttons Frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.download_button = ttk.Button(buttons_frame, text="Start Download", command=self.start_download)
        self.download_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(buttons_frame, text="Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(buttons_frame, text="Save API Credentials", command=self.save_credentials).pack(side=tk.RIGHT, padx=5)
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=2)
        
        # Log area
        self.log_area = scrolledtext.ScrolledText(progress_frame, height=15, wrap=tk.WORD)
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_area.config(state=tk.DISABLED)
    
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.download_folder.set(folder)
    
    def save_credentials(self):
        api_id = self.api_id.get().strip()
        api_hash = self.api_hash.get().strip()
        
        if not api_id or not api_hash:
            self.log_message("Error: API ID and API Hash cannot be empty")
            return
        
        # Create or update .env file
        with open('.env', 'w') as f:
            f.write(f"API_ID={api_id}\n")
            f.write(f"API_HASH={api_hash}\n")
        
        self.log_message("API credentials saved to .env file")
    
    def log_message(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
    
    def update_status(self, message):
        self.status_var.set(message)
    
    def update_progress(self, current, total):
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
    
    def start_download(self):
        # Validate inputs
        api_id = self.api_id.get().strip()
        api_hash = self.api_hash.get().strip()
        channel = self.channel_input.get().strip()
        
        if not api_id or not api_hash:
            self.log_message("Error: API ID and API Hash are required")
            return
        
        if not channel:
            self.log_message("Error: Channel username or URL is required")
            return
        
        # Update UI
        self.download_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_downloading = True
        
        # Start download in a separate thread
        threading.Thread(target=self.download_thread, daemon=True).start()
    
    def stop_download(self):
        self.is_downloading = False
        self.update_status("Download stopped")
        self.log_message("Download process stopped by user")
        self.download_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def download_thread(self):
        # Reset progress
        self.progress_var.set(0)
        
        # Create event loop for asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.download_process())
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
        finally:
            loop.close()
            
            # Update UI
            if self.is_downloading:  # Only if not stopped by user
                self.is_downloading = False
                self.root.after(0, lambda: self.download_button.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
    
    async def download_process(self):
        # Get parameters
        api_id = self.api_id.get().strip()
        api_hash = self.api_hash.get().strip()
        channel_input = self.channel_input.get().strip()
        download_folder = self.download_folder.get()
        file_types_input = self.file_types.get().strip()
        limit_input = self.message_limit.get().strip()
        
        # Parse file types
        file_types = set()
        if file_types_input:
            file_types = {ft.strip().lower() for ft in file_types_input.split(',')}
        
        # Parse limit
        limit = None
        if limit_input:
            try:
                limit = int(limit_input)
            except ValueError:
                self.log_message("Warning: Invalid message limit, using default (all messages)")
        
        # Create client
        self.log_message(f"Connecting to Telegram...")
        self.update_status("Connecting...")
        
        self.client = TelegramClient('telegram_downloader_session', api_id, api_hash)
        await self.client.start()
        
        if not await self.client.is_user_authorized():
            self.log_message("You need to log in to your Telegram account.")
            self.update_status("Authentication required")
            
            # This part is tricky in a GUI. For simplicity, we'll use a basic dialog
            phone_number = self.show_input_dialog("Enter your phone number:")
            if not phone_number:
                self.log_message("Authentication cancelled")
                await self.client.disconnect()
                return
            
            await self.client.send_code_request(phone_number)
            code = self.show_input_dialog("Enter the code you received:")
            if not code:
                self.log_message("Authentication cancelled")
                await self.client.disconnect()
                return
            
            try:
                await self.client.sign_in(phone_number, code)
            except Exception as e:
                self.log_message(f"Authentication error: {str(e)}")
                await self.client.disconnect()
                return
        
        me = await self.client.get_me()
        self.log_message(f"Logged in as {me.first_name}")
        
        # Get entity
        try:
            self.update_status("Finding channel...")
            self.log_message(f"Looking for channel: {channel_input}")
            
            entity = None
            
            # Handle web client URLs (e.g., https://web.telegram.org/k/#-1234567890)
            if 'web.telegram.org' in channel_input and '#' in channel_input:
                # Extract the channel ID from the URL
                channel_id_str = channel_input.split('#')[-1]
                
                # If it starts with a dash, it's likely a channel ID
                if channel_id_str.startswith('-'):
                    try:
                        # Convert to integer (Telegram channel IDs are integers)
                        channel_id = int(channel_id_str)
                        self.log_message(f"Trying to access channel with ID: {channel_id}")
                        
                        # For supergroups/channels, we need to use PeerChannel with the correct ID format
                        if str(channel_id).startswith('-100'):
                            peer_id = int(str(channel_id)[4:])  # Remove the -100 prefix
                        else:
                            # If it starts with just a dash, it might be a regular channel ID
                            if str(channel_id).startswith('-'):
                                peer_id = int(str(channel_id)[1:])  # Remove the dash
                            else:
                                peer_id = channel_id
                        
                        try:
                            from telethon.tl.types import PeerChannel, InputPeerChannel
                            # Try different approaches to get the entity
                            try:
                                # Try with PeerChannel
                                self.log_message(f"Trying PeerChannel approach with peer_id: {peer_id}")
                                entity = await self.client.get_entity(PeerChannel(peer_id))
                            except Exception as e1:
                                self.log_message(f"PeerChannel approach failed: {str(e1)}")
                                try:
                                    # Try with InputPeerChannel
                                    self.log_message(f"Trying InputPeerChannel approach")
                                    entity = await self.client.get_entity(InputPeerChannel(peer_id, 0))
                                except Exception as e2:
                                    self.log_message(f"InputPeerChannel approach failed: {str(e2)}")
                                    # Try with -100 prefix format
                                    self.log_message(f"Trying with -100 prefix format")
                                    channel_100_id = -1000000000000 - peer_id
                                    entity = await self.client.get_entity(channel_100_id)
                            
                            if entity:
                                self.update_status(f"Found channel with ID: {channel_id}")
                        except Exception as e:
                            self.log_message(f"All channel ID approaches failed: {str(e)}")
                    except ValueError:
                        self.log_message(f"Could not parse channel ID from {channel_id_str}")
                    except Exception as e:
                        self.log_message(f"Error accessing channel ID {channel_id_str}: {str(e)}")
            
            # If we haven't found the entity yet, try other methods
            if not entity:
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
                    try:
                        channel_id = int(channel_input)
                        self.log_message(f"Trying to access channel with ID: {channel_id}")
                        
                        # For supergroups/channels, we need to use the correct ID format
                        if str(channel_id).startswith('-100'):
                            # Already in the right format
                            try:
                                entity = await self.client.get_entity(channel_id)
                                self.update_status(f"Found channel with ID: {channel_id}")
                            except Exception as e:
                                self.log_message(f"Error with direct ID: {str(e)}")
                        elif str(channel_id).startswith('-'):
                            # Convert to proper format for channels/supergroups
                            try:
                                from telethon.tl.types import PeerChannel
                                peer_id = int(str(channel_id)[1:])  # Remove the dash
                                self.log_message(f"Trying PeerChannel with peer_id: {peer_id}")
                                entity = await self.client.get_entity(PeerChannel(peer_id))
                                self.update_status(f"Found channel with PeerChannel: {peer_id}")
                            except Exception as e:
                                self.log_message(f"PeerChannel approach failed: {str(e)}")
                                try:
                                    # Try with -100 prefix format
                                    channel_100_id = int(f"-100{str(channel_id)[1:]}")
                                    self.log_message(f"Trying with -100 prefix: {channel_100_id}")
                                    entity = await self.client.get_entity(channel_100_id)
                                    self.update_status(f"Found channel with -100 prefix: {channel_100_id}")
                                except Exception as e2:
                                    self.log_message(f"-100 prefix approach failed: {str(e2)}")
                                    try:
                                        # Last resort: try with large negative number format
                                        peer_id = int(str(channel_id)[1:])  # Remove the dash
                                        channel_100_id = -1000000000000 - peer_id
                                        self.log_message(f"Trying with special format: {channel_100_id}")
                                        entity = await self.client.get_entity(channel_100_id)
                                        self.update_status(f"Found channel with special format: {channel_100_id}")
                                    except Exception as e3:
                                        self.log_message(f"Special format approach failed: {str(e3)}")
                        else:
                            # Regular ID (not a channel/supergroup)
                            try:
                                entity = await self.client.get_entity(channel_id)
                                self.update_status(f"Found entity with ID: {channel_id}")
                            except Exception as e:
                                self.log_message(f"Error with direct ID: {str(e)}")
                    except Exception as e:
                        self.log_message(f"Error accessing channel ID {channel_input}: {str(e)}")
                
                # If we still haven't found the entity, try by username or other identifiers
                if not entity:
                    try:
                        self.log_message(f"Trying to access channel with identifier: {channel_input}")
                        entity = await self.client.get_entity(channel_input)
                        self.update_status(f"Found channel: {channel_input}")
                    except Exception as e:
                        self.log_message(f"Error accessing channel {channel_input}: {str(e)}")
            
            if not entity:
                self.log_message(f"Could not find channel: {channel_input}")
                await self.client.disconnect()
                return
            
            channel_name = getattr(entity, 'title', getattr(entity, 'username', channel_input))
            self.log_message(f"Found channel: {channel_name}")
            
            # Get messages
            self.update_status("Fetching messages...")
            self.log_message(f"Fetching up to {limit if limit else 'all'} messages...")
            
            messages = []
            async for message in self.client.iter_messages(entity, limit=limit):
                if not self.is_downloading:
                    break
                messages.append(message)
            
            if not self.is_downloading:
                self.log_message("Download stopped while fetching messages")
                await self.client.disconnect()
                return
            
            self.log_message(f"Found {len(messages)} messages")
            
            # Filter messages with media
            media_messages = [msg for msg in messages if msg.media]
            self.log_message(f"Found {len(media_messages)} messages with media")
            
            if not media_messages:
                self.log_message("No media files found in the channel")
                self.update_status("No files to download")
                await self.client.disconnect()
                return
            
            # Create download folder if it doesn't exist
            os.makedirs(download_folder, exist_ok=True)
            
            # Download files
            self.update_status("Downloading files...")
            downloaded_count = 0
            failed_count = 0
            
            for i, message in enumerate(media_messages):
                if not self.is_downloading:
                    break
                
                # Update progress
                progress_percent = (i / len(media_messages)) * 100
                self.progress_var.set(progress_percent)
                
                try:
                    if message.media:
                        # Determine file type
                        file_type = None
                        if isinstance(message.media, MessageMediaDocument):
                            doc = message.media.document
                            for attr in doc.attributes:
                                if hasattr(attr, 'file_name'):
                                    file_name = attr.file_name
                                    file_ext = os.path.splitext(file_name)[1].lower()[1:]
                                    file_type = file_ext
                                    break
                        elif isinstance(message.media, MessageMediaPhoto):
                            file_type = "photo"
                        
                        # Check if we want to download this file type
                        if not file_types or (file_type and file_type in file_types):
                            # Generate a unique filename
                            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                            msg_id = message.id
                            
                            # Determine file extension and name
                            if hasattr(message.media, 'document'):
                                for attr in message.media.document.attributes:
                                    if hasattr(attr, 'file_name'):
                                        file_name = f"{date_str}_{msg_id}_{attr.file_name}"
                                        break
                                else:
                                    mime_type = message.media.document.mime_type
                                    ext = mime_type.split('/')[1] if '/' in mime_type else 'unknown'
                                    file_name = f"{date_str}_{msg_id}.{ext}"
                            else:
                                # For photos
                                file_name = f"{date_str}_{msg_id}.jpg"
                            
                            # Full path for the file
                            file_path = os.path.join(download_folder, file_name)
                            
                            # Log download
                            self.log_message(f"Downloading: {file_name}")
                            self.update_status(f"Downloading: {file_name}")
                            
                            # Download the file
                            await self.client.download_media(message, file_path)
                            
                            self.log_message(f"Downloaded: {file_name}")
                            downloaded_count += 1
                except Exception as e:
                    self.log_message(f"Error downloading file: {str(e)}")
                    failed_count += 1
            
            # Final status
            if self.is_downloading:
                self.progress_var.set(100)
                self.update_status("Download complete")
                self.log_message(f"\nDownload summary:")
                self.log_message(f"Successfully downloaded: {downloaded_count} files")
                self.log_message(f"Failed downloads: {failed_count} files")
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
        finally:
            # Disconnect client
            if self.client:
                await self.client.disconnect()
    
    def show_input_dialog(self, prompt):
        # Simple dialog for input
        dialog = tk.Toplevel(self.root)
        dialog.title("Input Required")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=prompt).pack(pady=10)
        
        entry_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=entry_var, width=30)
        entry.pack(pady=5)
        entry.focus_set()
        
        result = [None]  # Use a list to store the result
        
        def on_ok():
            result[0] = entry_var.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Handle Enter key
        dialog.bind("<Return>", lambda event: on_ok())
        
        # Wait for the dialog to close
        self.root.wait_window(dialog)
        
        return result[0]

def main():
    root = tk.Tk()
    app = TelegramDownloaderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

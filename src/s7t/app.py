import asyncio
import tkinter as tk
from tkinter import filedialog
from s7t.config_manager import ConfigManager
import os
from pathlib import Path
import dbf
import httpx
import toga

from toga.style import Pack
from toga.style.pack import COLUMN, ROW


class BaseProcessor:
    """Base class for working with data sources."""

    def __init__(self, translator, logger):
        self.translator = translator
        self.logger = logger

    async def process(self):
        """Method to be implemented by child classes."""
        raise NotImplementedError("This method should be overridden.")


class DBProcessor(BaseProcessor):
    """Class for working with database files."""

    def __init__(self, root_dir, translator, logger, encoding):
        super().__init__(translator, logger)
        self.root_dir = root_dir
        self.encoding = encoding

    async def get_tables_with_comment_field(self, root_dir):
        """Check if DBF files have COMMENT or _COMMENT fields."""
        self.logger.log(f"Searching for COMMENT fields in {root_dir}")
        cnt = 0
        for root, _, files in os.walk(root_dir):
            for file in files:

                if file.lower().endswith(".dbf"):
                    file_path = Path(root) / file
                    table = None
                    try:
                        #print(str(file_path))
                        table = dbf.Table(str(file_path),ignore_memos=True, codepage=self.encoding)
                        table.open(mode=dbf.READ_WRITE)
                        keys = ['_SKZ', '_UNAME', 'NAME', 'LANGNAME', '_COMMENT', 'COMMENT']
                        entries = [(field, table.field_info(field)[1]) for field in table.field_names if field in keys]
                       # _SKZ _UNAME NAME LANGNAME
                        if any(entry[0] in {"COMMENT", "_COMMENT"} for entry in entries):
                            cnt+=1
                            self.logger.log(f"Table {file} contains COMMENT or _COMMENT field.", log_level=1)
                            print(entries)
                            for i, record in enumerate(table):
                                outputs= [record[rec[0]] for rec in entries]
                                print(outputs)
                                    # #print("I am here")
                                    # original_comment = (record.COMMENT or record._COMMENT, "")
                                    # if original_comment:
                                    #    translated_comment ="abra"# await self.translator.translate(original_comment)
                                    #     print(f"{original_comment=}  {translated_comment=}")
                                    #     #record["COMMENT" if "COMMENT" in record else "_COMMENT"] = translated_comment
                                    #     #record.store()
                                    #     #self.logger.log(f"Updated record {i + 1}/{total_records}: {translated_comment}")

                            #self.logger.log(f"Completed processing table {file}.", log_level=1)
                        else:
                            #self.logger.log(f"Table {file} does not contain COMMENT fields.")
                            # total_records = len(table)
                            pass

                    except Exception as e:
                        pass#self.logger.log(f"Error processing table {file}: {e}")
                    finally:
                        if table:  # Close table
                            table.close()
        self.logger.log(f"found {cnt} files", log_level=1)


    async def process(self):
        """Process all .dbf files."""
        self.logger.log(f"Starting database processing in {self.root_dir}.")
        await self.get_tables_with_comment_field(self.root_dir)

        self.logger.log(f"Finished processing all databases in {self.root_dir}.")


class Translator:
    """Class for translating text."""

    def __init__(self, target_language="en", logger=None):
        self.target_language = target_language
        self.logger = logger
        self.google_translate_api_url = "https://translate.googleapis.com/translate_a/single"

    async def translate(self, text):
        """Translate text using Google Translate API."""
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": self.target_language,
            "dt": "t",
            "q": text
        }
        async with httpx.AsyncClient() as client:
            self.logger.log(f"Translating: {text}")
            response = await client.get(self.google_translate_api_url, params=params)
            response.raise_for_status()
            return response.json()[0][0][0]


class TaskLogger:
    """Class for managing logs and progress."""

    def __init__(self, parent_box):
        self.log_box = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, padding=10))
        parent_box.add(self.log_box)

    def log(self, message, log_level=2):
        """Add a message to the logs."""
        match log_level:
            case 1:
                self.log_box.value += f"{message}\n"
            case 2:
                print(message)


class TranslationApp(toga.App):
    def startup(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN))

        # Initialize configuration manager
        try:
            self.config_manager = ConfigManager('config.json')
        except FileNotFoundError:
            self.logger.log("Error: 'config.json' not found. Using default settings.")
            self.config_manager = ConfigManager()  # Initialize with defaults

        # Load settings from config
        self.logger = TaskLogger(self.main_box)
        self.code_pages = self.config_manager.get("code_pages", {})
        self.encoding = self.config_manager.get("default_encoding", "cp1252")
        self.db_root_dir = self.config_manager.get("directories", {}).get("db_root_dir", "")

        self.translator = Translator(
            target_language=self.config_manager.get("translator_settings", {}).get("target_language", "en"),
            logger=self.logger
        )

        # Dropdown for code pages
        self.encodings_kv_swapped = {v: k for k, v in self.code_pages.items()}
        self.dropdown = toga.Selection(items=list(self.encodings_kv_swapped.keys()), style=Pack(padding=5))
        self.dropdown.value = self.dropdown.value = self.code_pages.get(self.encoding)
        self.main_box.add(self.dropdown)

        self.dropdown.on_change = self.on_encoding_change

        # Create the main window and set its content
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box
        self.main_window.show()

        # Create the application menu
        self.create_menu()

    def create_menu(self):
        """Create the application menu."""
        self.logger.log("Creating menu.")
        self.commands.add(
            toga.Command(self.select_db_directory, text="Select Database Directory", group=toga.Group.FILE),
            toga.Command(self.process_databases, text="Process Databases", group=toga.Group("Processing")),
        )

    async def select_db_directory(self, widget):
        """Open a dialog to select the database directory."""
        selected_dir = await self.main_window.select_folder_dialog(title="Select Database Directory")
        if selected_dir:
            self.db_root_dir = Path(selected_dir)
            self.logger.log(f"Selected database directory: {selected_dir}")

    async def process_databases(self, widget):
        """Start database processing."""
        if not self.db_root_dir:
            self.logger.log("Database directory is not selected.")
            return
        self.logger.log("Starting database processing...")
        db_processor = DBProcessor(self.db_root_dir, self.translator, self.logger, self.encoding)
        await db_processor.process()

    def on_encoding_change(self, widget):
        """Handle encoding change from dropdown."""
        new_encoding = self.encodings_kv_swapped.get(widget.value)
        self.config_manager.update("default_encoding", new_encoding)
        self.logger.log(f"Encoding changed to {new_encoding} --> {widget.value}")



def main():
    return TranslationApp()

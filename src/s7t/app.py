import asyncio
import tkinter as tk
from tkinter import filedialog
import os
from pathlib import Path
import devart.xbase
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

    def __init__(self, root_dir, translator, logger):
        super().__init__(translator, logger)
        self.root_dir = root_dir

    def get_tables_with_comment_field(self, root_dir):
        """Check if db has interesting us fields(_COMMENT)."""
        self.logger.log(f"SEARCHING IN  {root_dir} ")
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith(".dbf"):
                    self.logger.log(f"Trying to enter {file} in {root}")
                    cursor = None
                    connection = None
                    try:
                        connection = devart.xbase.connect(Database=Path(root), CodePage='WesternEuropeanANSI')
                        cursor = connection.cursor()
                        # Retrieving table fields
                        cursor.execute(f"PRAGMA table_info({Path(file).stem})")
                        fields = cursor.fetchall()
                        # Check if comments exist
                        if any(field[1] in {"COMMENT", "_COMMENT"} for field in fields):
                            self.logger.log(f"Table {Path(file).stem} contains field 'COMMENT' or '_COMMENT'.", log_level=1)
                            result = {'name': Path(file).stem, 'file_path': Path(root)}
                            print(f"####{result}")
                            yield result
                        else:
                            self.logger.log(f"Table {Path(file).stem} doesn't contain comment field.")

                    except Exception as e:
                        self.logger.log(f"Error handling file {file}: {e}")
                    finally:
                        if cursor:
                            cursor.close()
                        if connection:
                            connection.close()

    async def process_table(self, file_path, table_name):
        """Process a table with a COMMENT field."""
        self.logger.log(f"Processing table {table_name} in folder {file_path}.", log_level=1)
        # connection = devart.xbase.connect(Database=file_path, CodePage='WesternEuropeanANSI')
        # cursor = connection.cursor()
        #
        # # Retrieve records
        # cursor.execute(f"SELECT * FROM {table_name}")
        # rows = cursor.fetchall()
        #
        # total_records = len(rows)
        # #self.logger.set_task_progress(file_path.name, table_name, 0, total_records)
        #
        # for i, row in enumerate(rows):
        #     #record_id = row[0]
        #     original_comment = row[1] or ""
        #     #translated_comment = await self.translator.translate(original_comment)
        #     #self.logger.log(translated_comment)
        #     #cursor.execute(f"UPDATE {table_name} SET COMMENT = ? WHERE ID = ?",
        #     #               (translated_comment, record_id))
        #     self.logger.log(f"{table_name=}:::{i}:::{row}")
        #     #self.logger.update_task_progress(file_path.name, table_name, i + 1)
        #
        # connection.commit()
        # cursor.close()
        # connection.close()
        self.logger.log(f"Completed processing table {table_name} in file {file_path.name}.", log_level=1)

    async def process(self):
        """Process all .dbf files."""
        self.logger.log(f"Starting database processing in directory {self.root_dir}.")
        # func should be itterable
        ## I consider implementation async task processing here

        for table in self.get_tables_with_comment_field(self.root_dir):
            print(table)
            await self.process_table(file_path=table['file_path'], table_name=table['name'])

        self.logger.log(f"Finished processing all databases in directory {self.root_dir}.")


class TextFileProcessor(BaseProcessor):
    """Class for processing text files."""

    def __init__(self, root_dir, translator, logger):
        super().__init__(translator, logger)
        self.root_dir = root_dir


    async def process(self):
        self.logger.log(f"Not implememented yet...")
    #
    # TO DO
    #

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
            self.logger.log(f"translating:{text}")
            response = await client.get(self.google_translate_api_url, params=params)
            response.raise_for_status()
            return response.json()[0][0][0]


class TaskLogger:
    """Class for managing logs and progress."""

    def __init__(self, parent_box):
        self.log_box = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, padding=10))
        self.progress_bars = {}
        parent_box.add(self.log_box)

    def log(self, message, log_level=2):
        """Add a message to the logs."""
        match log_level:
            case 1:
                self.log_box.value += f"{message}\n"
            case 2:
                print(message)

    def set_task_progress(self, file_name, task_name, current, total):
        """Initialize a progress bar for a task."""
        key = f"{file_name}:{task_name}"
        if key not in self.progress_bars:
            progress_bar = toga.ProgressBar(max=total, style=Pack(padding=(5, 10)))
            self.progress_bars[key] = progress_bar
            self.log_box.parent.add(progress_bar)

    def update_task_progress(self, file_name, task_name, current):
        """Update progress bar value."""
        key = f"{file_name}:{task_name}"
        if key in self.progress_bars:
            self.progress_bars[key].value = current


class TranslationApp(toga.App):
    """Toga application for managing the processing workflow."""

    def startup(self):
        main_box = toga.Box(style=Pack(direction=COLUMN))
        self.logger = TaskLogger(main_box)
        self.translator = Translator(logger=self.logger)

        # Initially, root directories are not selected
        self.db_root_dir = "/home/wt/D2"# None
        self.text_root_dir = None

        # Create menu
        self.create_menu()

        # Main content of the window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def create_menu(self):
        """Create the application menu."""
        self.logger.log("Creating menu.")
        self.commands.add(
            toga.Command(self.select_db_directory, text="Select Database Directory", group=toga.Group.FILE),
            toga.Command(self.select_text_directory, text="Select Text File Directory", group=toga.Group.FILE),
        )

        process_menu = toga.Group("Processing")
        self.commands.add(
            toga.Command(self.process_databases, text="Process Databases", group=process_menu),
            toga.Command(self.process_texts, text="Process Text Files", group=process_menu),
        )

    def select_directory(self, title):
        """Open system dialog to select a directory using tkinter."""
        self.logger.log(f"Opening directory selection dialog: {title}")
        root = tk.Tk()
        root.withdraw()  # Hide main Tkinter window
        directory = filedialog.askdirectory(title=title)
        root.destroy()  # Destroy the window after selection
        return directory

    async def select_db_directory(self, widget):
        """Open dialog to select the database directory."""
        self.logger.log("Opening database directory selection dialog.")
        selected_dir = self.select_directory("Select Database Directory")
        if selected_dir:
            self.db_root_dir = Path(selected_dir)
            self.logger.log(f"Selected database directory: {selected_dir}")

    async def select_text_directory(self, widget):
        """Open dialog to select the text file directory."""
        self.logger.log("Opening text file directory selection dialog.")
        selected_dir = self.select_directory("Select Text File Directory")
        if selected_dir:
            self.text_root_dir = Path(selected_dir)
            self.logger.log(f"Selected text file directory: {selected_dir}")

    async def process_databases(self, widget):
        """Start database processing."""
        if self.db_root_dir is None:
            self.logger.log("Database directory is not selected.")
            return
        self.logger.log("Starting database processing...")
        db_processor = DBProcessor(self.db_root_dir, self.translator, self.logger)
        await db_processor.process()

    async def process_texts(self, widget):
        """Start text file processing."""
        if self.text_root_dir is None:
            self.logger.log("Text file directory is not selected.")
            return
        self.logger.log("Starting text file processing...")
        text_processor = TextFileProcessor(self.text_root_dir, self.translator, self.logger)
        await text_processor.process()


def main():
    return TranslationApp()

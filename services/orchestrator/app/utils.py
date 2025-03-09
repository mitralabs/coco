import os
from pathlib import Path
import logging
import sys

from typing import Dict, Optional, Tuple, List

ROOT_PATH = Path(os.getenv("AUDIO_ROOT_PATH", "/data/audio"))

# Directory structure constants
DIR_RAW = "raw"
# DIR_PROCESSED = "processed"
DIR_TRANSCRIPTS = "transcripts"
SUBDIRECTORIES = [DIR_RAW, DIR_TRANSCRIPTS]  # DIR_PROCESSED
TEMP_FILENAME = "temp.wav"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class AudioPathManager:
    """Manages audio file paths and directory structure"""

    def __init__(self, root_path: Path = ROOT_PATH):
        self.root_path = root_path

    def ensure_directory_exists(self, directory: Path) -> None:
        """Create directory if it doesn't exist"""
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

    def get_session_path(self, parsed_filename: Dict[str, str]) -> Path:
        """Get the base session path and ensure directories exist"""
        # Ensure root directory exists
        self.ensure_directory_exists(self.root_path)

        # Create session directory name
        session_folder = (
            f"recordings_{parsed_filename['file_date']}_{parsed_filename['session_id']}"
        )
        session_path = self.root_path / session_folder

        # Ensure session directory exists
        self.ensure_directory_exists(session_path)

        # Ensure subdirectories exist
        for subfolder in SUBDIRECTORIES:
            self.ensure_directory_exists(session_path / subfolder)

        return session_path

    def get_raw_path(self, filename: str) -> Optional[Path]:
        """Get path for raw audio file"""
        parsed = parse_coco_filename(filename)
        if not parsed:
            return None

        session_path = self.get_session_path(parsed)

        # Optionally reformat the filename
        processed_filename = filename

        return session_path / DIR_RAW / processed_filename

    def get_transcript_path(self, audio_path: str) -> str:
        """Convert audio path to transcript path"""
        # Ensure we're working with a string
        audio_path_str = str(audio_path)
        return audio_path_str.replace(f"/{DIR_RAW}/", f"/{DIR_TRANSCRIPTS}/").replace(
            ".wav", ".txt"
        )


# Initialize the path manager
path_manager = AudioPathManager(ROOT_PATH)


def parse_coco_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse a filename following the format int_int_YY-DD-MM_HH-MM-SS_suffix.wav
    Returns a dictionary with the parsed components or None if invalid
    """
    if not filename.endswith(".wav"):
        return None

    parts = filename.split("_")
    if len(parts) != 5:
        return None

    session_id, index, ymd, hms, suffix_with_ext = parts
    suffix = suffix_with_ext.split(".")[0]

    # Basic validation
    if not (session_id.isdigit() and index.isdigit()):
        return None
    if not (ymd.count("-") == 2 and hms.count("-") == 2):
        return None
    if suffix not in ["start", "end", "middle"]:
        return None

    return {
        "session_id": session_id,
        "file_index": index,
        "file_date": ymd,
        "file_time": hms,
        "suffix": suffix,
    }


# For backward compatibility
def get_path(root: Path = ROOT_PATH, filename: str = "") -> Optional[Path]:
    """Legacy function for backward compatibility"""
    return path_manager.get_raw_path(filename)


def process_transcription(transcription: str, audio_path: str) -> str:
    # (1) save it to a file, and (2) create new "full_transcript" from all existing transcripts.
    # Swap /post/ with /transcripts/ in audio_path, and swap .wav with .txt

    logger.info(f"Processing transcription for audio: {audio_path}")
    file_path = path_manager.get_transcript_path(audio_path)
    file_directory = os.path.dirname(file_path)

    if not os.path.exists(file_directory):
        os.makedirs(file_directory)
        logger.info(f"Created transcript directory: {file_directory}")

    try:
        with open(file_path, "w") as f:
            f.write(transcription)
        logger.info(f"Transcription saved successfully to: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save transcription: {str(e)}")

    # Include logic to create the full transcript, once every snippet from the audio is transcribed.

    ##############################
    # IMPLEMENTATION FOR FULL TRANSCRIPT, WILL BE ADDED LATER
    ##############################

    return file_path


def post_process_audio(file_path: str) -> list:
    # Currently only returns the file_path.
    # Only addition will be an overlap of audio snippets to ensure no words are missed.
    # This will be implemented later.

    return [file_path]

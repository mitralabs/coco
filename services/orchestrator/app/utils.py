import os
from pathlib import Path
import logging
import sys
import datetime
from typing import Dict, Optional, Tuple, List

ROOT_PATH = Path(os.getenv("AUDIO_ROOT_PATH", "/data"))

# Directory structure constants
DIR_RAW = "raw"
DIR_TRANSCRIPTS = "transcripts"
SUBDIRECTORIES = [DIR_RAW, DIR_TRANSCRIPTS]

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

    def save_transcription(self, transcription: str, audio_path: str) -> str:
        """
        Save a transcription for an audio file and return the file path
        """
        logger.info(f"Processing transcription for audio: {audio_path}")
        file_path = self.get_transcript_path(audio_path)
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

        return file_path

    def get_prompt(self, audio_path: str) -> Optional[str]:
        """
        Get the transcription of the previous audio snippet to use as context
        for transcribing the current audio snippet.

        Args:
            audio_path: Path to the current audio file

        Returns:
            The content of the previous transcript or None if not available
        """
        # Extract filename from path
        audio_filename = os.path.basename(audio_path)

        # Parse the filename to get components
        parsed = parse_coco_filename(audio_filename)
        if not parsed:
            logger.error(f"Invalid filename format: {audio_filename}")
            return None

        # Get the current file index and session ID
        try:
            current_index = int(parsed["file_index"])
            session_id = parsed["session_id"]
        except ValueError:
            logger.error(f"Invalid file index: {parsed['file_index']}")
            return None

        # If this is the first file, there's no previous context
        if current_index <= 0:
            logger.info(
                "First audio snippet in sequence, no previous context available"
            )
            return None

        # Calculate the previous index
        prev_index = current_index - 1

        # Get the transcript directory path
        transcript_dir = os.path.dirname(self.get_transcript_path(audio_path))

        if not os.path.exists(transcript_dir):
            logger.info(f"Transcript directory does not exist: {transcript_dir}")
            return None

        # Find any file matching the session ID and previous index
        prev_transcript = None
        for file in os.listdir(transcript_dir):
            if file.endswith(".txt"):
                parsed_file = parse_coco_filename(file, is_transcript=True)
                if (
                    parsed_file
                    and parsed_file["session_id"] == session_id
                    and int(parsed_file["file_index"]) == prev_index
                ):
                    prev_transcript = os.path.join(transcript_dir, file)
                    break

        if not prev_transcript:
            logger.info(f"No previous transcript found for index {prev_index}")
            return None

        # Read the content of the previous transcript
        try:
            with open(prev_transcript, "r") as f:
                transcript_content = f.read()
            logger.info(f"Retrieved previous transcript: {prev_transcript}")
            return transcript_content
        except Exception as e:
            logger.error(f"Failed to read previous transcript: {str(e)}")
            return None

    def get_date(self, audio_path: str) -> Optional[datetime.datetime]:
        """
        Extract date and time from an audio file path and return as datetime object

        Args:
            audio_path: Path to the audio file

        Returns:
            datetime.datetime object or None if parsing fails
        """
        # Extract filename from path
        audio_filename = os.path.basename(audio_path)

        # Parse the filename to get components
        parsed = parse_coco_filename(audio_filename)
        if not parsed:
            logger.error(f"Invalid filename format: {audio_filename}")
            return None

        # Extract date and time components
        try:
            # Parse date (YY-MM-DD format per filename convention)
            date_parts = parsed["file_date"].split("-")
            if len(date_parts) != 3:
                raise ValueError(f"Invalid date format: {parsed['file_date']}")

            year = int("20" + date_parts[0])  # Assuming 20YY format
            month = int(date_parts[1])
            day = int(date_parts[2])

            # Parse time (HH-MM-SS format)
            time_parts = parsed["file_time"].split("-")
            if len(time_parts) != 3:
                raise ValueError(f"Invalid time format: {parsed['file_time']}")

            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2])

            # Create datetime object
            date_obj = datetime.datetime(year, month, day, hour, minute, second)
            logger.info(f"Successfully parsed date: {date_obj} from {audio_filename}")
            return date_obj
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse date/time from {audio_path}: {str(e)}")
            return None

    def get_session_id_and_index(self, audio_path: str) -> Optional[Tuple[str, str]]:
        """
        Extract the session ID and file index from an audio file path

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple of (session_id, file_index) or None if parsing fails
        """
        # Extract filename from path
        audio_filename = os.path.basename(audio_path)

        # Parse the filename to get components
        parsed = parse_coco_filename(audio_filename)
        if not parsed:
            logger.error(f"Invalid filename format: {audio_filename}")
            return None

        return (parsed["session_id"], parsed["file_index"])


def parse_coco_filename(
    filename: str, is_transcript: bool = False
) -> Optional[Dict[str, str]]:
    """
    Parse a filename following the format int_int_YY-MM-DD_HH-MM-SS_suffix.wav (or .txt)
    Returns a dictionary with the parsed components or None if invalid

    Args:
        filename: The filename to parse
        is_transcript: If True, accepts .txt extension instead of .wav
    """
    valid_extension = ".txt" if is_transcript else ".wav"
    if not filename.endswith(valid_extension):
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
        "session_id": int(session_id),
        "file_index": int(index),
        "file_date": ymd,
        "file_time": hms,
        "suffix": suffix,
    }


# Initialize the path manager
PathManager = AudioPathManager(ROOT_PATH)

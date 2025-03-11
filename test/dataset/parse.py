import csv
from datetime import datetime


def parse_csv_to_dataset(csv_path):
    """
    Parse a CSV file with semicolon delimiters and multiline entries,
    and convert it to a Hugging Face dataset.

    The CSV has the format:
    - Semicolon (;) delimiters
    - Multiline entries in quotes (")
    - Chunks and Chunk Dates columns have entries separated by "==="

    Args:
        csv_path: Path to the CSV file

    Returns:
        A Hugging Face dataset
    """
    data = {"question": [], "answer": [], "chunks": [], "chunk_datetimes": []}

    with open(csv_path, "r", encoding="utf-8") as f:
        # Using csv.reader with ; as delimiter and " as quotechar
        reader = csv.reader(f, delimiter=";", quotechar='"')

        # Skip header row
        header = next(reader)

        for i, row in enumerate(reader):
            if len(row) >= 4:  # Ensure row has at least 4 columns
                question = row[0]
                answer = row[1]
                chunks = row[2].split("===") if row[2] else []
                chunk_datetimes = row[3].split("===") if row[3] else []

                # Strip whitespace from chunks and chunk_dates
                chunks = [chunk.strip() for chunk in chunks]
                chunk_datetimes = [
                    datetime.strptime(dt.strip(), "%Y-%m-%d %H-%M")
                    for dt in chunk_datetimes
                ]

                assert len(chunks) == len(
                    chunk_datetimes
                ), f"Row {i} has {len(chunks)} chunks and {len(chunk_datetimes)} chunk datetimes"

                data["question"].append(question)
                data["answer"].append(answer)
                data["chunks"].append(chunks)
                data["chunk_datetimes"].append(chunk_datetimes)

    return data

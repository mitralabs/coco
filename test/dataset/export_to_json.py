import csv
import json
from pathlib import Path
from datetime import datetime


def load_csv_dataset(csv_file_path):
    """Load dataset from CSV file and return as list of dictionaries with combined chunks."""
    data = []

    with open(csv_file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        header = next(reader)

        for row in enumerate(reader):
            if len(row[1]) >= 4:  # Ensure row has at least 4 columns
                item = {}

                # Extract basic fields
                for i, field_name in enumerate(header):
                    if i < len(row[1]):
                        item[field_name] = row[1][i]

                # Process chunks and chunk datetimes
                chunks = row[1][2].split("===") if row[1][2] else []
                chunk_datetimes = row[1][3].split("===") if row[1][3] else []

                # Strip whitespace
                chunks = [chunk.strip() for chunk in chunks]
                chunk_datetimes = [dt.strip() for dt in chunk_datetimes]

                # Combine chunks and datetimes into a list
                combined_chunks = []
                for j in range(min(len(chunks), len(chunk_datetimes))):
                    combined_chunks.append(
                        {"text": chunks[j], "datetime": chunk_datetimes[j]}
                    )

                item["chunks"] = combined_chunks

                # Remove the original separate fields
                if "Chunks" in item:
                    del item["Chunks"]
                if "Chunk Datetimes" in item:
                    del item["Chunk Datetimes"]

                data.append(item)

    return data


def load_negative_chunks(csv_file_path):
    """Load negative chunks from CSV and combine text and datetime."""
    data = []

    with open(csv_file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        header = next(reader)

        for row in reader:
            if len(row) >= 2:
                item = {"text": row[0], "datetime": row[1]}
                data.append(item)

    return data


def export_to_json():
    """Export all CSV datasets to JSON format."""
    base_dir = Path(__file__).parent
    datasets_dir = base_dir / "datasets_by_category"
    json_output_dir = base_dir / "datasets_json"

    # Create output directory if it doesn't exist
    json_output_dir.mkdir(exist_ok=True)

    # Process category datasets
    for csv_file in datasets_dir.glob("*.csv"):
        data = load_csv_dataset(csv_file)

        # Save to JSON
        json_file = json_output_dir / f"{csv_file.stem}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Exported {csv_file.name} to {json_file.name}")

    # Process negative chunks
    negative_file = base_dir / "negative_chunks.csv"
    if negative_file.exists():
        data = load_negative_chunks(negative_file)

        # Save to JSON in the base directory instead of json_output_dir
        json_file = base_dir / "negative_chunks.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(
            f"Exported negative_chunks.csv to negative_samples.json (in base directory)"
        )


if __name__ == "__main__":
    export_to_json()

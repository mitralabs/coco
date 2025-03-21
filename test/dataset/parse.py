import csv
import json
from pathlib import Path
from datetime import datetime


def get_dataset(dataset_file: Path) -> dict:
    """Load single dataset (category) from csv file.

    Args:
        dataset_file (Path): Path to csv file with dataset.

    Returns:
        dict: {
            "question": list[str],
            "answer": list[str],
            "chunks": list[list[str]],
            "chunk_datetimes": list[list[datetime]],
        }
    """
    data = {"question": [], "answer": [], "chunks": [], "chunk_datetimes": []}

    if dataset_file.suffix.lower() == ".json":
        return get_json_dataset(dataset_file)

    with dataset_file.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        header = next(reader)

        for i, row in enumerate(reader):
            if len(row) >= 4:  # Ensure row has at least 4 columns
                question = row[0]
                answer = row[1]
                chunks = row[2].split("===") if row[2] else []
                chunk_datetimes = row[3].split("===") if row[3] else []

                # Strip whitespace from chunks and chunk_dates
                chunks = [chunk.strip() for chunk in chunks]
                try:
                    chunk_datetimes = [
                        datetime.strptime(dt.strip(), "%Y-%m-%d %H-%M")
                        for dt in chunk_datetimes
                    ]
                except Exception as e:
                    print(
                        f"Error parsing datetime for row {i + 1}: {e} of dataset: {dataset_file}"
                    )

                assert len(chunks) == len(
                    chunk_datetimes
                ), f"Row {i + 1} of {dataset_file} has {len(chunks)} chunks and {len(chunk_datetimes)} chunk datetimes"

                data["question"].append(question)
                data["answer"].append(answer)
                data["chunks"].append(chunks)
                data["chunk_datetimes"].append(chunk_datetimes)

    return data


def get_json_dataset(dataset_file: Path) -> dict:
    """Load single dataset (category) from json file.

    Args:
        dataset_file (Path): Path to json file with dataset.

    Returns:
        dict: {
            "question": list[str],
            "answer": list[str],
            "chunks": list[list[str]],
            "chunk_datetimes": list[list[datetime]],
        }
    """
    data = {"question": [], "answer": [], "chunks": [], "chunk_datetimes": []}

    with dataset_file.open("r", encoding="utf-8") as f:
        json_data = json.load(f)

        for i, item in enumerate(json_data):
            if "Question" in item and "Answer" in item and "chunks" in item:
                question = item["Question"]
                answer = item["Answer"]

                chunk_texts = []
                chunk_dates = []

                for chunk in item["chunks"]:
                    if "text" in chunk and "datetime" in chunk:
                        chunk_texts.append(chunk["text"])
                        try:
                            dt = datetime.strptime(chunk["datetime"], "%Y-%m-%d %H-%M")
                            chunk_dates.append(dt)
                        except Exception as e:
                            print(
                                f"Error parsing datetime for item {i + 1}: {e} of dataset: {dataset_file}"
                            )

                assert len(chunk_texts) == len(
                    chunk_dates
                ), f"Item {i + 1} of {dataset_file} has {len(chunk_texts)} chunks and {len(chunk_dates)} chunk datetimes"

                data["question"].append(question)
                data["answer"].append(answer)
                data["chunks"].append(chunk_texts)
                data["chunk_datetimes"].append(chunk_dates)

    return data


def get_datasets(samples_path: str) -> dict:
    """Load all datasets (categories) from csv and json files in samples directory.

    Args:
        samples_path (str): Path to directory with csv/json files with datasets.

    Returns:
        dict: {
            "category_name": dataset,
            ...
        }
    """
    samples_dir = Path(samples_path)
    datasets = {}
    for dataset_file in samples_dir.glob("*.csv"):
        datasets[dataset_file.stem] = get_dataset(dataset_file)
    for dataset_file in samples_dir.glob("*.json"):
        datasets[dataset_file.stem] = get_dataset(dataset_file)
    return datasets


def merge_datasets(datasets: dict) -> dict:
    """Merge all datasets into single dataset.

    Args:
        datasets (dict): Dictionary with keys: category name, value: dataset.

    Returns:
        dict: Merged dataset.
    """
    full_ds = {
        "question": [],
        "answer": [],
        "chunks": [],
        "chunk_datetimes": [],
    }
    for dataset in datasets.values():
        full_ds["question"].extend(dataset["question"])
        full_ds["answer"].extend(dataset["answer"])
        full_ds["chunks"].extend(dataset["chunks"])
        full_ds["chunk_datetimes"].extend(dataset["chunk_datetimes"])
    return full_ds


def get_negative_chunks(negatives_path: str) -> dict:
    """Load negative chunks and datetimes from csv or json file.

    Args:
        negatives_path (str): Path to csv or json file with negative chunks and datetimes.

    Returns:
        dict: {
            "chunks": list[str],
            "chunk_datetimes": list[datetime],
        }
    """
    negatives_file = Path(negatives_path)
    chunks, datetimes = [], []

    if negatives_file.suffix.lower() == ".json":
        with negatives_file.open("r", encoding="utf-8") as f:
            json_data = json.load(f)

            for item in json_data:
                if "text" in item and "datetime" in item:
                    chunks.append(item["text"])
                    try:
                        dt = datetime.strptime(item["datetime"], "%Y-%m-%d %H-%M")
                        datetimes.append(dt)
                    except Exception as e:
                        print(f"Error parsing datetime in negative chunks: {e}")
    else:
        with negatives_file.open("r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            header = next(reader)

            for row in reader:
                if len(row) >= 2:
                    chunk = row[0]
                    chunk_datetime = row[1]

                    chunks.append(chunk)
                    try:
                        dt = datetime.strptime(chunk_datetime, "%Y-%m-%d %H-%M")
                        datetimes.append(dt)
                    except Exception as e:
                        print(f"Error parsing datetime in negative chunks: {e}")

    return {"chunks": chunks, "chunk_datetimes": datetimes}


def get_all_chunks(merged_dataset: dict, negatives: dict) -> dict:
    """Get all chunks and datetimes from datasets and negatives.

    Args:
        merged_dataset (dict): Merged dataset.
        negatives (dict): Negative chunks and datetimes.

    Returns:
        dict: {
            "chunks": list[str],
            "chunk_datetimes": list[datetime],
        }
    """
    ds_chunks = [chunk for chunks in merged_dataset["chunks"] for chunk in chunks]
    ds_datetimes = [
        dt for datetimes in merged_dataset["chunk_datetimes"] for dt in datetimes
    ]

    all_chunks = negatives["chunks"] + ds_chunks
    all_chunk_datetimes = negatives["chunk_datetimes"] + ds_datetimes

    return {
        "chunks": all_chunks,
        "chunk_datetimes": all_chunk_datetimes,
    }

import json
import argparse
from pathlib import Path


def load_data(json_path: Path) -> dict:
    """Loads data from the specified JSON file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_path}")
        return None


def display_samples(data: dict, category_filter: str | None = None):
    """Displays samples, optionally filtered by category."""
    if not data:
        return

    chunks_by_id = {chunk["id"]: chunk for chunk in data.get("chunks", [])}
    all_samples = data.get("samples", [])

    samples_by_category = {}
    for category_data in all_samples:
        category_name = category_data.get("category")
        if category_name not in samples_by_category:
            samples_by_category[category_name] = []
        samples_by_category[category_name].extend(category_data.get("samples", []))

    categories_to_display = samples_by_category.keys()
    if category_filter:
        if category_filter in samples_by_category:
            categories_to_display = [category_filter]
        else:
            print(f"Error: Category '{category_filter}' not found.")
            print(f"Available categories: {', '.join(samples_by_category.keys())}")
            return

    for category in categories_to_display:
        print(f"--- Category: {category} ---")
        print("-" * (len(category) + 18))  # Separator line

        category_samples = samples_by_category[category]
        if not category_samples:
            print("No samples found for this category.")
            continue

        for i, sample in enumerate(category_samples):
            print(f"\n[Sample {i+1}/{len(category_samples)}]")
            print(f"  Query: {sample.get('query', 'N/A')}")
            print(f"  GT Answer: {sample.get('gt_answer', 'N/A')}")
            print("  Chunks:")
            chunk_ids = sample.get("chunk_ids", [])
            if chunk_ids:
                for chunk_id in chunk_ids:
                    chunk_data = chunks_by_id.get(chunk_id)
                    if chunk_data:
                        chunk_text = chunk_data.get(
                            "text", f"Chunk ID {chunk_id} text not found."
                        )
                        chunk_datetime = chunk_data.get("datetime", "No datetime found")
                        print(f"    [ID: {chunk_id}] [Datetime: {chunk_datetime}]")
                        # Indent chunk text for readability
                        indented_text = "\n".join(
                            ["      " + line for line in chunk_text.split("\n")]
                        )
                        print(indented_text)
                    else:
                        print(f"    Chunk ID {chunk_id} not found.")
                    print("-" * 10)  # Separator between chunks
            else:
                print("    No chunk IDs specified.")
        print(" ")  # Add space after the last sample of a category


def main():
    parser = argparse.ArgumentParser(
        description="Display samples from new.json, optionally filtered by category."
    )
    parser.add_argument(
        "-c",
        "--category",
        type=str,
        help="Specify a category to display samples for (e.g., language_sentiment, multi_query). Displays all if not specified.",
        default=None,
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    json_file_path = script_dir / "new.json"

    data = load_data(json_file_path)
    display_samples(data, args.category)


if __name__ == "__main__":
    main()

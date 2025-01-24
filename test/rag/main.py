from datasets import load_dataset
from pathlib import Path
import time
from datetime import timedelta
from coco import CocoClient, rag_query

cc = CocoClient(
    chunking_base="http://127.0.0.1:8001",
    embedding_base="http://127.0.0.1:8002",
    db_api_base="http://127.0.0.1:8003",
    transcription_base="http://127.0.0.1:8000",
    api_key="test",
)


def format_duration(duration_seconds: float) -> str:
    """Format duration in seconds to minutes, seconds, and milliseconds."""
    td = timedelta(seconds=duration_seconds)
    minutes = td.seconds // 60
    seconds = td.seconds % 60
    milliseconds = round(td.microseconds / 1000)
    return f"{minutes}m {seconds}s {milliseconds}ms"


def init_dataset():
    ds_name = "deepset/germandpr"
    data_dir = Path("data") / "germandpr"
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    ds = load_dataset(ds_name, cache_dir=data_dir)
    train_ds, test_ds = ds["train"], ds["test"]
    return train_ds, test_ds


def unique_texts(ds, verbose=False):
    """
    Extract unique texts from the dataset.

    Args:
        ds (Dataset): The dataset to extract unique texts from.
        verbose (bool, optional): Whether to print verbose output. Defaults to False.

    Returns:
        list: A list of tuples (text, title)
    """
    pos, neg, hard_neg = [], [], []
    for sample in ds:
        p = sample["positive_ctxs"]
        for title, text in zip(p["text"], p["title"]):
            pos.append((title, text))
        n = sample["negative_ctxs"]
        for title, text in zip(n["text"], n["title"]):
            neg.append((title, text))
        hn = sample["hard_negative_ctxs"]
        for title, text in zip(hn["text"], hn["title"]):
            hard_neg.append((title, text))
    merged = list(set(pos + neg + hard_neg))
    if verbose:
        print("pos", len(pos))
        print("neg", len(neg))
        print("hard_neg", len(hard_neg))
        print("sum", len(pos) + len(neg) + len(hard_neg))
        print("merged", len(merged))
        print("merged_unique_titles", len(set([title for _, title in merged])))
        print("merged_unique_texts", len(set([text for text, _ in merged])))
    return merged


def main():
    total_start = time.time()

    # Load dataset
    dataset_start = time.time()
    train_ds, _ = init_dataset()
    unique = unique_texts(train_ds)
    texts = [text for text, _ in unique]  # don't use titles for now
    texts = texts[:300]  # ! tmp
    dataset_duration = time.time() - dataset_start
    print(f"\nDataset loading completed in {format_duration(dataset_duration)}")

    # Get example query and ground truth
    query = train_ds[0]["question"]
    print("\nQuery:")
    print(query)
    print()

    gt_context = train_ds[0]["positive_ctxs"]["text"]
    print("Ground Truth Context:")
    print(gt_context)
    print()

    gt_answer = train_ds[0]["answers"][0]
    print("Ground Truth Answer:")
    print(gt_answer)
    print()

    print("=" * 50)
    print()

    # Create embeddings
    embedding_start = time.time()
    embeddings = cc.embedding.create_embeddings(texts, show_progress=True)
    embedding_duration = time.time() - embedding_start
    print(f"Embedding creation completed in {format_duration(embedding_duration)}")

    # Store in database
    storage_start = time.time()
    cc.db_api.store_in_database(texts, embeddings, "de", "germandpr")
    storage_duration = time.time() - storage_start
    print(f"Database storage completed in {format_duration(storage_duration)}")

    # Query RAG system
    rag_start = time.time()
    answer = rag_query(cc.db_api, query, verbose=True)
    rag_duration = time.time() - rag_start
    print(f"RAG query completed in {format_duration(rag_duration)}")

    print("\nGenerated Answer:")
    print(answer)

    # Print timing summary
    total_duration = time.time() - total_start
    print("\nTiming Summary:")
    print(f"Dataset Loading: {format_duration(dataset_duration)}")
    print(f"Embedding:       {format_duration(embedding_duration)}")
    print(f"Storage:         {format_duration(storage_duration)}")
    print(f"RAG Query:       {format_duration(rag_duration)}")
    print(f"Total Time:      {format_duration(total_duration)}")

    # clear database
    cc.db_api.clear_database()


if __name__ == "__main__":
    main()

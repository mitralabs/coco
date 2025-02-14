from datasets import load_dataset, concatenate_datasets, Dataset
from pathlib import Path
from omegaconf import DictConfig
import logging
import wandb
import shutil

from coco import CocoClient

logger = logging.getLogger(__name__)


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


def init_dataset(cfg: DictConfig) -> Dataset:
    ds = load_dataset(cfg.data.hf_name, trust_remote_code=True)
    train_ds, test_ds = ds["train"], ds["test"]
    datasets = []
    if cfg.data.use_train:
        datasets.append(train_ds)
    if cfg.data.use_test:
        datasets.append(test_ds)
    if len(datasets) == 0:
        logger.error(
            "No datasets splits specified, set either use_train or use_test or both"
        )
        wandb.finish()
        exit(1)
    return concatenate_datasets(datasets)


def backup_database(cfg: DictConfig):
    if not cfg.data.backup_db:
        logger.info("Skipping database backup")
        return
    db_path = Path(cfg.general.services_data_dir) / "db"
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.error(
            "set the data path correctly or disable backup if no database exists yet"
        )
        wandb.finish()
        exit(1)
    backup_path = Path(cfg.general.services_data_dir) / ("db_before_" + cfg.wandb.name)
    if backup_path.exists():
        logger.warning(f"Backup path {backup_path} already exists, skipping backup")
        return
    shutil.copytree(db_path, backup_path)
    logger.info(f"Backed up database to {backup_path}")


def clear_database(cc: CocoClient, cfg: DictConfig):
    if not cfg.data.clear_db:
        logger.info("Skipping database clearing")
        return
    deleted_count = cc.db_api.clear_database()
    logger.info(f"Cleared database: {deleted_count} chunks")


def fill_database(cc: CocoClient, cfg: DictConfig, dataset: Dataset):
    if cfg.data.fill_db.skip:
        logger.info(f"Skipping {cfg.data.name} to db")
        return
    unique = unique_texts(dataset)
    texts = [text for text, _ in unique]  # don't use titles for now
    added, skipped = cc.embed_and_store(
        chunks=texts,
        language=cfg.data.language,
        filename=cfg.data.name,
        model=cfg.data.fill_db.embedding_model,
        batch_size=cfg.data.fill_db.embed_and_store_batch_size,
        limit_parallel=cfg.data.fill_db.embed_and_store_limit_parallel,
        show_progress=True,
    )
    logger.info(f"Added {cfg.data.name} to db: {added} added, {skipped} skipped")


def data_stage(cc: CocoClient, cfg: DictConfig) -> Dataset:
    ds = init_dataset(cfg)
    if cfg.data.limit_samples:
        ds = ds.select(range(cfg.data.limit_samples))
    backup_database(cfg)
    clear_database(cc, cfg)
    fill_database(cc, cfg, ds)
    return ds

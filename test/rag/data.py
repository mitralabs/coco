from datasets import load_dataset, concatenate_datasets, Dataset
from pathlib import Path
from omegaconf import DictConfig
import logging
import wandb
import shutil
from coco import CocoClient
import sys
import random
import datetime

sys.path.append("../dataset")

import parse  # type: ignore
from dataset import RAGDataset

logger = logging.getLogger(__name__)


def get_hf_dpr_dataset(cfg: DictConfig) -> Dataset:
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


def random_dt(
    from_dt: datetime.datetime = datetime.datetime(2021, 1, 1, 0, 0, 0),
    to_dt: datetime.datetime = datetime.datetime(2025, 12, 31, 23, 59, 59),
) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(
        random.uniform(from_dt.timestamp(), to_dt.timestamp())
    )


def fill_database(cc: CocoClient, cfg: DictConfig, dataset: RAGDataset):
    if cfg.data.fill_db.skip:
        logger.info(f"Skipping {cfg.data.name} to db")
        return
    model_emb_dim = cc.lm.get_embedding_dim(cfg.retrieval.embedding_model[0])
    db_emb_dim = cc.db_api.get_max_embedding_dim()
    assert (
        model_emb_dim <= db_emb_dim
    ), f"Embedding model {cfg.retrieval.embedding_model[0]} has dimension {model_emb_dim} which is greater than the maximum supported dimension {db_emb_dim}"
    chunks, chunk_datetimes = dataset.unique_chunks()
    if cfg.data.random_datetimes_if_missing:
        chunk_datetimes = [dt or random_dt() for dt in chunk_datetimes]
    added, skipped = cc.embed_and_store_multiple(
        chunks=chunks,
        language=cfg.data.language,
        filename=cfg.data.name,
        date_times=chunk_datetimes,
        model=cfg.retrieval.embedding_model[0],
        batch_size=cfg.data.fill_db.embed_and_store_batch_size,
        limit_parallel=cfg.data.fill_db.embed_and_store_limit_parallel,
        show_progress=True,
    )
    logger.info(f"Added {cfg.data.name} to db: {added} added, {skipped} skipped")


def data_stage(cc: CocoClient, cfg: DictConfig) -> Dataset:
    logger.info(f"Starting data stage")
    if cfg.data.type == "hf_dpr":
        hf_dpr_dataset = get_hf_dpr_dataset(cfg)
        ds = RAGDataset.from_dpr_dataset(hf_dpr_dataset)
    elif cfg.data.type == "custom":
        custom_datasets = parse.get_datasets(samples_path=cfg.data.custom_samples_root)
        ds = RAGDataset.from_custom_datasets(custom_datasets)
    else:
        logger.error(f"Invalid dataset type: {cfg.data.type}")
        wandb.finish()
        exit(1)
    if cfg.data.limit_samples:
        ds = ds[: cfg.data.limit_samples]
    backup_database(cfg)
    clear_database(cc, cfg)
    fill_database(cc, cfg, ds)
    logger.info(f"Data stage completed")
    return ds

import hydra
from omegaconf import DictConfig, OmegaConf
import wandb
import logging
from coco import CocoClient
import random
import numpy as np

from data import data_stage
from retrieval import retrieval_stage
from generation import generation_stage


logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("absl").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(logging.WARNING)
logging.getLogger("coco.tools").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    logger.info(f"Config:\n{OmegaConf.to_yaml(cfg)}")

    random.seed(cfg.general.random_seed)
    np.random.seed(cfg.general.random_seed)

    wandb.init(
        entity=cfg.wandb.entity,
        project=cfg.wandb.project,
        name=cfg.wandb.name,
        config=OmegaConf.to_container(cfg),
        settings=wandb.Settings(start_method="thread"),
    )

    cc = CocoClient(
        **cfg.coco,
        embedding_api=cfg.retrieval.embedding_model[1],
        llm_api=cfg.generation.llm_model[1],
    )
    cc.health_check()

    coco_conf_oai = cfg.coco.copy()
    coco_conf_oai["openai_base"] = "https://api.openai.com/v1"
    cc_oai = CocoClient(
        **coco_conf_oai,
        embedding_api=cfg.retrieval.embedding_model[1],
        llm_api=cfg.generation.llm_model[1],
        tools_coco_client=cc,
    )
    cc_oai.health_check()

    ds = data_stage(cc, cfg)
    top_chunks = retrieval_stage(cc, cfg, ds)
    generation_stage(cc, cc_oai, cfg, ds, top_chunks)

    wandb.finish()


if __name__ == "__main__":
    main()

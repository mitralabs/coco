import hydra
from omegaconf import DictConfig, OmegaConf
import wandb
import logging
from coco import CocoClient

from data import handle_data
from retrieval import handle_retrieval
from generation import handle_generation


logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# def rag():
#     train_ds, _ = init_dataset()
#     query = train_ds[0]["question"]
#     print("\nQuery:")
#     print(query)
#     print()

#     gt_context = train_ds[0]["positive_ctxs"]["text"]
#     print("Ground Truth Context:")
#     print(gt_context)
#     print()

#     gt_answer = train_ds[0]["answers"][0]
#     print("Ground Truth Answer:")
#     print(gt_answer)
#     print()

#     print("=" * 50)
#     print()

#     rag_start = time.time()
# answer, tok_s = rag_query(cc.db_api, query, verbose=True)
#     rag_duration = time.time() - rag_start

#     print(
#         f"\nGenerated Answer (took {format_duration(rag_duration)} with {tok_s} tokens/s):"
#     )
#     print(answer)


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    logger.info(f"Config:\n{OmegaConf.to_yaml(cfg)}")

    wandb.init(
        entity=cfg.wandb.entity,
        project=cfg.wandb.project,
        name=cfg.wandb.name,
        config=OmegaConf.to_container(cfg),
    )

    cc = CocoClient(**cfg.coco)
    ds = handle_data(cc, cfg)
    handle_retrieval(cc, cfg, ds)
    handle_generation(cc, cfg)

    wandb.finish()


if __name__ == "__main__":
    main()

from datasets import load_dataset
import pprint
from pathlib import Path


def main():
    ds_name = "deepset/germandpr"

    data_dir = Path("data") / "germandpr"
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    ds = load_dataset(ds_name, cache_dir=data_dir)
    train_ds, test_ds = ds["train"], ds["test"]
    pprint.pprint(train_ds[0]["hard_negative_ctxs"])


if __name__ == "__main__":
    main()

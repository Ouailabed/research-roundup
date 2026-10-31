from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_sources():
    with open(ROOT / "config" / "sources.yaml", encoding="utf-8") as file:
        return yaml.safe_load(file)["sources"]


if __name__ == "__main__":
    for source in load_sources():
        print(source["name"])

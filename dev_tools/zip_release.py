import argparse
import shutil
from pathlib import Path


ADDON_DIR_NAME = "Modifier_List_Fork"
ITEMS_TO_INCLUDE = (
    "icons",
    "modules",
    "__init__.py",
    "addon_registration.py",
    "LICENSE"
)


def parse_args():
    parser = argparse.ArgumentParser()
    return parser.parse_args()


def get_dir_content_to_ignore(src: str, names: list[str]):
    return [name for name in names if name == "__pycache__"]


def main():
    root = Path(__file__).resolve().parents[2]
    zip_name = f"{ADDON_DIR_NAME}"
    temp_dir = root / f"{ADDON_DIR_NAME}_temp"

    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    temp_dir.mkdir()

    for item in ITEMS_TO_INCLUDE:
        source = root / ADDON_DIR_NAME / item
        dest = temp_dir / item
        if source.is_dir():
            shutil.copytree(source, dest, ignore=get_dir_content_to_ignore)
        else:
            shutil.copy(source, dest)

    shutil.make_archive(root / zip_name, "zip", temp_dir)

    print(f"{zip_name}.zip succesfully created")

    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

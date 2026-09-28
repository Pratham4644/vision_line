import asyncio
import sys
from pathlib import Path
from pprint import pprint

ROOT_DIR = Path(__file__).resolve()

for parent in ROOT_DIR.parents:
    if (parent / "backend").is_dir():
        sys.path.insert(0, str(parent))
        break

from backend.app.db import db


async def main():
    await db.connect()

    try:
        sites = await db.sites.find({}).to_list(length=100)

        print(f"Found {len(sites)} site(s):\n")

        for site in sites:
            site.pop("_id", None)
            pprint(site)
            print("-" * 80)

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
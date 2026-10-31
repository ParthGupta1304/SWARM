"""Reset an explicitly configured disposable Bazaar DB."""

import argparse

from bazaar.database import settings
from bazaar.seed import seed_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    seed_database(settings.database_url, args.seed)
    print(f"Seeded disposable Bazaar with seed={args.seed}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Migrate legacy user_memory rows into the 3-layer memory system."""

from __future__ import annotations

import asyncio
import sys

from src.memory.database import init_db
from src.memory.migrate import migrate_all_legacy


async def main() -> int:
    await init_db()
    count = await migrate_all_legacy()
    print(f"Migrated {count} user(s) from legacy user_memory.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

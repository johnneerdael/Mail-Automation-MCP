from __future__ import annotations

import asyncio
import logging

from workspace_secretary.executor.imap_executor import ExecutorConfig, run_forever


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever(ExecutorConfig()))


if __name__ == "__main__":
    main()

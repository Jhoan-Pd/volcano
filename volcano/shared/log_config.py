"""One logging set-up for the three services, so every line says which process wrote it.

    2026-11-10 14:03:21 INFO engine volcano.engine.rpc: Predict → OK in 12 ms
"""
import logging
import os


def configure_logging(service: str, level: str | None = None) -> None:
    logging.basicConfig(
        level=(level or os.getenv("LOG_LEVEL", "INFO")).upper(),
        format=f"%(asctime)s %(levelname)s {service} %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

import logging
import logging.handlers
import os

from app.settings import Settings, init_working_dir
from app.ui.main_window import MainWindow
from app.data import logo_cache


def _setup_logging(working_dir: str) -> None:
    log_dir  = os.path.join(working_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "cfb_stat_card_maker.log")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler — keep last 5 × 1 MB logs
    fh = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # Console handler for WARNING+ only (visible when running from terminal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s  %(name)s  %(message)s"))
    root.addHandler(ch)

    logging.getLogger(__name__).info("CFB Stat Card Maker started. Log: %s", log_path)


def main() -> None:
    default_cfg_dir = Settings().working_dir
    os.makedirs(default_cfg_dir, exist_ok=True)
    settings = Settings.load(default_cfg_dir)
    init_working_dir(settings.working_dir)
    logo_cache.set_api_key(settings.cfbd_api_key)
    _setup_logging(settings.working_dir)
    app = MainWindow(settings)
    app.mainloop()
    logging.getLogger(__name__).info("CFB Stat Card Maker exited.")

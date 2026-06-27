"""日志模块 — 文件轮转 + 定期清理 + 控制台输出"""

import logging
import os
import time
from datetime import datetime, timedelta


class LogManager:
    def __init__(self, log_dir: str = "logs", retention_days: int = 7):
        self.log_dir = log_dir
        self.retention_days = retention_days

    def setup(self) -> logging.Logger:
        os.makedirs(self.log_dir, exist_ok=True)
        self.cleanup_old_logs()

        logger = logging.getLogger("DeepSeekAutoQA")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 文件 Handler：每天一个文件
        fh = logging.FileHandler(self.get_log_path(), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # 控制台 Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        return logger

    def cleanup_old_logs(self):
        if not os.path.isdir(self.log_dir):
            return
        cutoff = time.time() - self.retention_days * 86400
        for fname in os.listdir(self.log_dir):
            if not fname.startswith("log_") or not fname.endswith(".log"):
                continue
            fpath = os.path.join(self.log_dir, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass

    def get_log_path(self) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"log_{date_str}.log")

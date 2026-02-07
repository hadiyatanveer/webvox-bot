"""
Logging utility for WebVox.
Provides centralized logging configuration for all modules.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "webvox",
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_dir: Optional[str] = None,
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    Set up a logger with file and/or console handlers.
    
    Args:
        name: Logger name
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        log_dir: Directory for log files (default: logs/)
        level: Logging level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        if log_dir is None:
            project_root = Path(__file__).parent.parent
            log_dir = project_root / "logs"
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{name}_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        print(f"📝 Logging to: {log_file}")
    
    return logger


def get_test_logger(test_name: str = "test_end_to_end") -> logging.Logger:
    """Get a logger configured for test output."""
    return setup_logger(
        name=test_name,
        log_to_file=True,
        log_to_console=True,  # Keep console output too
        level=logging.DEBUG
    )


# Convenience function to redirect all print statements
class LoggerWriter:
    """Redirect print statements to logger."""
    
    def __init__(self, logger: logging.Logger, level: int = logging.INFO):
        self.logger = logger
        self.level = level
        self.buffer = ""
    
    def write(self, message: str):
        if message.strip():
            self.logger.log(self.level, message.strip())
    
    def flush(self):
        pass


def redirect_prints_to_logger(logger: logging.Logger):
    """Redirect all print statements to the logger."""
    sys.stdout = LoggerWriter(logger, logging.INFO)


def restore_prints():
    """Restore normal print behavior."""
    sys.stdout = sys.__stdout__

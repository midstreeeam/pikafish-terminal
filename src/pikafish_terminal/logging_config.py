import logging
import os
import sys
from pathlib import Path


def setup_logging(log_level = None, log_file = None) -> logging.Logger:
    """Set up logging configuration for the pikafish terminal application."""
    
    # Get log level from environment variable, default to INFO
    if log_level is None:
        log_level = os.getenv('PIKAFISH_LOG_LEVEL', 'INFO').upper()
    
    # Validate log level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level not in valid_levels:
        log_level = 'INFO'
    
    # Create logger
    logger = logging.getLogger('pikafish')
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Optionally create file handler if log file is specified
    if log_file is None:
        log_file = os.getenv('PIKAFISH_LOG_FILE')
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(logging.DEBUG)  # File gets all messages
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not create log file {log_file}: {e}")
    
    return logger


def get_logger(name: str = 'pikafish') -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name) 
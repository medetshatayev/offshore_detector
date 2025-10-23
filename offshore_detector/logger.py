"""
Centralized logging configuration.
Provides structured logging with PII redaction.
"""
import logging
import sys
import re
from config import LOG_LEVEL, LOG_FORMAT


def redact_account_number(text: str) -> str:
    """
    Redact account numbers, showing only last 4 digits.
    
    Args:
        text: Text that may contain account numbers
    
    Returns:
        Text with account numbers redacted
    """
    # Pattern for account numbers (assuming they're numeric sequences of 10+ digits)
    pattern = r'\b(\d{6,})(\d{4})\b'
    return re.sub(pattern, r'****\2', text)


class PIIRedactingFormatter(logging.Formatter):
    """
    Custom formatter that redacts PII from log messages.
    """
    
    def format(self, record):
        # Format the original message
        formatted = super().format(record)
        
        # Redact account numbers
        formatted = redact_account_number(formatted)
        
        return formatted


def setup_logging(name: str = None) -> logging.Logger:
    """
    Set up logging with PII redaction.
    
    Args:
        name: Logger name (defaults to root logger)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(LOG_LEVEL)
        
        # Console handler with PII redaction
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(LOG_LEVEL)
        
        formatter = PIIRedactingFormatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger


# Configure root logger
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set formatter to redacting version
for handler in logging.root.handlers:
    handler.setFormatter(PIIRedactingFormatter(LOG_FORMAT))

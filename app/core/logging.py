import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Regex to scrub sensitive keys, auth tokens, passwords, bearer tokens
SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{8,}'),
    re.compile(r'(?i)(api[_-]?key["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9_\-\.]{8,}'),
    re.compile(r'(?i)(token["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9_\-\.]{8,}'),
    re.compile(r'(?i)(secret["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9_\-\.]{8,}'),
    re.compile(r'(?i)(password["\']?\s*[:=]\s*["\']?)[^\s,"\']+'),
]

def scrub_sensitive_data(text: str) -> str:
    """Ensure no secrets, API keys, or tokens ever appear in logs."""
    if not isinstance(text, str):
        text = str(text)
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(r'\1[REDACTED_SECRET]', text)
    return text

class JsonLogFormatter(logging.Formatter):
    """Structured JSON log formatter meeting Integration Standard 8."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": scrub_sensitive_data(record.getMessage()),
            "logger": record.name,
            "job_id": getattr(record, "job_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
        }
        
        # Include extra attributes if provided
        if hasattr(record, "extra_data") and record.extra_data:
            # Clean extra data recursively
            log_entry["details"] = json.loads(scrub_sensitive_data(json.dumps(record.extra_data)))
            
        if record.exc_info:
            log_entry["exception"] = scrub_sensitive_data(self.formatException(record.exc_info))
            
        return json.dumps(log_entry)

def setup_logger(name: str = "incubrix") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger

logger = setup_logger()

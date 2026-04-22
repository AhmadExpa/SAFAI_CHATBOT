"""
Centralized logging configuration for the application.
Handles Unicode encoding issues on Windows console.
"""

import logging
import sys
import os
from typing import Optional

class UnicodeSafeFormatter(logging.Formatter):
    """Custom formatter that handles Unicode characters safely on Windows"""
    
    def format(self, record):
        try:
            # Try to format normally first
            return super().format(record)
        except UnicodeEncodeError:
            # If Unicode encoding fails, create a safe version
            try:
                # Create a copy of the record with safe message
                safe_record = logging.LogRecord(
                    record.name, record.levelno, record.pathname, 
                    record.lineno, record.msg, record.args, record.exc_info
                )
                
                # Replace the message with a safe version
                if hasattr(record, 'msg') and record.msg:
                    safe_record.msg = self._make_safe(record.msg)
                
                # Format the safe record
                return super().format(safe_record)
            except Exception:
                # Ultimate fallback - return a basic message
                return f"{record.levelname}: {record.name}: [Unicode content filtered]"

    def _make_safe(self, text):
        """Convert Unicode text to ASCII-safe version"""
        if isinstance(text, str):
            # Replace common Unicode characters with ASCII equivalents
            replacements = {
                '😊': ':)',
                '😢': ':(',
                '😀': ':D',
                '😁': ':D',
                '😂': ':D',
                '🤔': '?',
                '👍': '+',
                '👎': '-',
                '❤️': '<3',
                '💯': '100',
                '🔥': 'hot',
                '✨': '*',
                '🎉': 'party',
                '🚀': 'rocket',
                '💡': 'idea',
                '⭐': '*',
                '🌟': '*',
                '🎯': 'target',
                '📝': 'note',
                '📊': 'chart',
                '🔍': 'search',
                '⚡': 'fast',
                '🎨': 'art',
                '🎵': 'music',
                '🎮': 'game',
                '🏆': 'trophy',
                '🎪': 'circus',
                '🎭': 'theater',
                '🎨': 'art',
                '🎬': 'movie',
                '🎯': 'target',
                '🎲': 'dice',
                '🎳': 'bowling',
                '🎸': 'guitar',
                '🎺': 'trumpet',
                '🎻': 'violin',
                '🎼': 'music',
                '🎽': 'running',
                '🎾': 'tennis',
                '🎿': 'skiing',
                '🏀': 'basketball',
                '🏁': 'finish',
                '🏂': 'snowboard',
                '🏃': 'running',
                '🏄': 'surfing',
                '🏅': 'medal',
                '🏆': 'trophy',
                '🏇': 'horse',
                '🏈': 'football',
                '🏉': 'rugby',
                '🏊': 'swimming',
                '🏋': 'weight',
                '🏌': 'golf',
                '🏍': 'motorcycle',
                '🏎': 'racing',
                '🏏': 'cricket',
                '🏐': 'volleyball',
                '🏑': 'hockey',
                '🏒': 'hockey',
                '🏓': 'pingpong',
                '🏔': 'mountain',
                '🏕': 'camping',
                '🏖': 'beach',
                '🏗': 'construction',
                '🏘': 'houses',
                '🏙': 'city',
                '🏚': 'house',
                '🏛': 'building',
                '🏜': 'desert',
                '🏝': 'island',
                '🏞': 'park',
                '🏟': 'stadium',
                '🏠': 'house',
                '🏡': 'house',
                '🏢': 'office',
                '🏣': 'post',
                '🏤': 'post',
                '🏥': 'hospital',
                '🏦': 'bank',
                '🏧': 'atm',
                '🏨': 'hotel',
                '🏩': 'love',
                '🏪': 'store',
                '🏫': 'school',
                '🏬': 'store',
                '🏭': 'factory',
                '🏮': 'lantern',
                '🏯': 'castle',
                '🏰': 'castle',
                '🏱': 'flag',
                '🏲': 'flag',
                '🏳': 'flag',
                '🏴': 'flag',
                '🏵': 'rosette',
                '🏶': 'flag',
                '🏷': 'label',
                '🏸': 'badminton',
                '🏹': 'bow',
                '🏺': 'pot',
                '🏻': 'light',
                '🏼': 'medium',
                '🏽': 'medium',
                '🏾': 'dark',
                '🏿': 'dark',
            }
            
            # Apply replacements
            for unicode_char, ascii_replacement in replacements.items():
                text = text.replace(unicode_char, ascii_replacement)
            
            # For any remaining Unicode characters, replace with '?'
            try:
                return text.encode('ascii', 'replace').decode('ascii')
            except:
                return text.replace('?', '?')
        
        return text

def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None):
    """
    Set up logging configuration with Unicode-safe handling.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional file to write logs to
    """
    # Remove any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create formatter
    formatter = UnicodeSafeFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with Unicode-safe encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Set encoding to UTF-8 if possible, fallback to ASCII
    try:
        if hasattr(console_handler.stream, 'reconfigure'):
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        # Fallback for older Python versions or systems that don't support reconfigure
        pass
    
    # Add console handler
    logging.root.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logging.root.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file {log_file}: {e}")
    
    # Set level
    logging.root.setLevel(level)
    
    # Configure specific loggers
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    # Suppress httpx INFO logs (404s for expired images are expected)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Test the configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully with Unicode-safe handling")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name"""
    return logging.getLogger(name)

# Initialize logging when module is imported
setup_logging()

import os
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

def load_json(file_path: str, default_data: Any) -> Any:
    """
    Load JSON data from a file with error handling.
    
    Args:
        file_path: Path to the JSON file
        default_data: Default data to return if file doesn't exist or is invalid
        
    Returns:
        Loaded JSON data or default_data if file doesn't exist or is invalid
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default_data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return default_data

def save_json(file_path: str, data: Any) -> None:
    """
    Save data as JSON to a file, ensuring the directory exists.
    
    Args:
        file_path: Path where to save the JSON file
        data: Data to save as JSON
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

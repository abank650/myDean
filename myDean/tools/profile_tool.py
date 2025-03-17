from typing import Dict, Any, Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated as AnnotatedType
import json
import os

VALID_MAJORS = [
    "Bachelor of Science in Computer Science (B.S.)",
    "Bachelor of Arts in Computer Science (A.B.)",
    "Bachelor of Arts in Computer Science, Ethics, and Society (CSES)"
]

VALID_MINORS = [
    "Minor in Computer Science",
    "Concentration in Technology, Ethics, and Society"
]

VALID_PROFILE_KEYS = {
    "name": str,
    "grade": str,
    "school": str,
    "majors": list,
    "minors": list,
    "courses_completed": list
}

PROFILE_PATH = "data/profiles/"

def _ensure_profile_dir():
    """Ensure the profiles directory exists"""
    os.makedirs(PROFILE_PATH, exist_ok=True)

def _get_profile_path(user_id: str) -> str:
    """Get the full path for a user's profile file"""
    return os.path.join(PROFILE_PATH, f"{user_id}.json")

@tool
def get_profile(
    *,
    config: AnnotatedType[RunnableConfig, "InjectedToolArg"]
) -> Dict[str, Any]:
    """
    Retrieve the user's complete profile from file storage.
    
    Returns:
        Dict containing the user's profile information including name, grade, school,
        majors, minors, and completed courses.
    """
    user_id = config["configurable"].get("user_id", "default_user")
    _ensure_profile_dir()
    profile_path = _get_profile_path(user_id)
    
    try:
        with open(profile_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return empty profile if none exists
        return {k: None if v is str else [] for k, v in VALID_PROFILE_KEYS.items()}

@tool
def update_profile(
    updates: Dict[str, Any],
    *,
    config: AnnotatedType[RunnableConfig, "InjectedToolArg"]
) -> str:
    """
    Update specific fields in the user's profile.
    
    Args:
        updates: Dictionary containing the fields to update and their new values.
            For list fields (like majors, minors, courses_completed), you can:
            1. Replace the entire list by providing a new list
            2. Add/remove items using a dict with "add" and/or "remove" keys
            
            Examples:
            # Replace major (switching programs)
            {"majors": ["Bachelor of Science in Computer Science (B.S.)"]}
            
            # Add a second major
            {"majors": {"add": ["Bachelor of Science in Computer Science (B.S.)"]}}
            
            # Remove a course
            {"courses_completed": {"remove": ["COSC 2010"]}}
    
    Returns:
        String confirming the update
    """
    user_id = config["configurable"].get("user_id", "default_user")
    _ensure_profile_dir()
    profile_path = _get_profile_path(user_id)
    
    # Validate updates
    for key, value in updates.items():
        if key not in VALID_PROFILE_KEYS:
            raise ValueError(f"Invalid profile key: {key}")
            
        expected_type = VALID_PROFILE_KEYS[key]
        if expected_type is list:
            if not (isinstance(value, list) or 
                   (isinstance(value, dict) and all(k in ['add', 'remove'] for k in value.keys()))):
                raise ValueError(f"Invalid type for {key}: expected list or dict with 'add'/'remove' keys")
        elif not isinstance(value, expected_type):
            raise ValueError(f"Invalid type for {key}: expected {expected_type}, got {type(value)}")
        
        # Additional validation for majors and minors
        if key == "majors":
            values_to_check = value if isinstance(value, list) else value.get('add', [])
            invalid_majors = [m for m in values_to_check if m not in VALID_MAJORS]
            if invalid_majors:
                raise ValueError(f"Invalid major(s): {invalid_majors}. Valid majors are: {VALID_MAJORS}")
        elif key == "minors":
            values_to_check = value if isinstance(value, list) else value.get('add', [])
            invalid_minors = [m for m in values_to_check if m not in VALID_MINORS]
            if invalid_minors:
                raise ValueError(f"Invalid minor(s): {invalid_minors}. Valid minors are: {VALID_MINORS}")
    
    # Get existing profile or create new one
    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    except FileNotFoundError:
        profile = {k: None if v is str else [] for k, v in VALID_PROFILE_KEYS.items()}
    
    # Update profile
    for key, value in updates.items():
        if isinstance(value, list):
            # For list fields with direct list value, REPLACE the existing values
            profile[key] = value
        elif isinstance(value, dict) and VALID_PROFILE_KEYS[key] is list:
            # Handle add/remove operations for list fields
            existing_values = set(profile[key]) if profile[key] else set()
            if 'add' in value:
                existing_values.update(value['add'])
            if 'remove' in value:
                existing_values.difference_update(value['remove'])
            profile[key] = list(existing_values)
        else:
            profile[key] = value
    
    # Store updated profile
    with open(profile_path, 'w') as f:
        json.dump(profile, f, indent=2)
    
    return f"Successfully updated profile fields: {', '.join(updates.keys())}" 
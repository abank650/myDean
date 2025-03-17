from typing import Dict, Any, Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated as AnnotatedType
import json
import os
import re

# Constants for exact program names
PROGRAM_NAMES = {
    "majors": {
        "BS": "Bachelor of Science in Computer Science (B.S.)",
        "AB": "Bachelor of Arts in Computer Science (A.B.)",
        "CSES": "Bachelor of Arts in Computer Science Ethics and Society (CSES)"
    },
    "minors": {
        "CS": "Minor in Computer Science",
        "TES": "Technology Ethics and Society"
    }
}

# Common variations of program names for matching
PROGRAM_NAME_VARIATIONS = {
    # Major variations
    "bs": "Bachelor of Science in Computer Science (B.S.)",
    "b.s.": "Bachelor of Science in Computer Science (B.S.)",
    "bachelor of science": "Bachelor of Science in Computer Science (B.S.)",
    "ab": "Bachelor of Arts in Computer Science (A.B.)",
    "a.b.": "Bachelor of Arts in Computer Science (A.B.)",
    "bachelor of arts": "Bachelor of Arts in Computer Science (A.B.)",
    "cses": "Bachelor of Arts in Computer Science Ethics and Society (CSES)",
    "ethics": "Bachelor of Arts in Computer Science Ethics and Society (CSES)",
    # Minor variations
    "cs minor": "Minor in Computer Science",
    "computer science minor": "Minor in Computer Science",
    "minor cs": "Minor in Computer Science",
    "minor in cs": "Minor in Computer Science",
    "tes": "Technology Ethics and Society",
    "tech ethics": "Technology Ethics and Society"
}

def normalize_program_name(program: str) -> str:
    """
    Normalize program name to match the official names in requirements.
    Returns None if no match is found.
    """
    if not program:
        return None
    
    # If it's already an exact match, return it
    for category in PROGRAM_NAMES.values():
        if program in category.values():
            return program
    
    # Try to match variations
    normalized = PROGRAM_NAME_VARIATIONS.get(program.lower().strip())
    return normalized

REQUIREMENTS_FILE = "data/degree_requirements.json"

def matches_pattern(course_code: str, patterns: list) -> bool:
    """Check if a course code matches any of the given patterns"""
    return any(re.match(pattern, course_code) for pattern in patterns)

def normalize_course_code(course_code: str) -> str:
    """Normalize course code format to use dashes"""
    return course_code.replace(" ", "-")

@tool
def get_degree_requirements(program: str = None) -> Dict[str, Any]:
    """
    Retrieve degree requirements. If program is specified, only return requirements for that program.
    
    Args:
        program: Optional. The specific program to get requirements for. Can use common variations
                (e.g., "CS Minor", "AB", "Bachelor of Arts", etc.)
    """
    with open(REQUIREMENTS_FILE, 'r') as f:
        all_requirements = json.load(f)
    
    if not program:
        return all_requirements
    
    normalized_program = normalize_program_name(program)
    if not normalized_program:
        return {"error": f"Program '{program}' not recognized. Valid programs are: {list(PROGRAM_NAMES['majors'].values()) + list(PROGRAM_NAMES['minors'].values())}"}
    
    result = {}
    
    # Check if it's a major
    if normalized_program in all_requirements["majors"]:
        result["majors"] = {normalized_program: all_requirements["majors"][normalized_program]}
        if "math_requirements" in all_requirements["majors"][normalized_program]:
            result["valid_math_electives"] = all_requirements["valid_math_electives"]
    
    # Check if it's a minor
    elif normalized_program in all_requirements["minors"]:
        result["minors"] = {normalized_program: all_requirements["minors"][normalized_program]}
    
    return result or {"error": f"Program '{normalized_program}' not found in requirements"}

@tool
def check_requirements_progress(
    config: Annotated[RunnableConfig, "InjectedToolArg"],
    program: str = None
) -> Dict[str, Any]:
    """
    Check progress towards completing major/minor requirements based on completed courses.
    
    Args:
        config: The config object containing user_id
        program: Optional. The specific program to check progress for. Can use common variations
                (e.g., "CS Minor", "AB", "Bachelor of Arts", etc.)
    """
    user_id = config["configurable"].get("user_id", "default_user")
    
    # Get user's profile
    profile_path = f"data/profiles/{user_id}.json"
    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    except FileNotFoundError:
        return {"error": "Profile not found"}
    
    # Normalize all completed courses to use dashes
    normalized_courses = [normalize_course_code(c) for c in profile.get("courses_completed", [])]
    
    # Get degree requirements
    with open(REQUIREMENTS_FILE, 'r') as f:
        requirements = json.load(f)
    
    progress = {}
    
    # If program is specified, only check that program
    if program:
        normalized_program = normalize_program_name(program)
        if not normalized_program:
            return {"error": f"Program '{program}' not recognized. Valid programs are: {list(PROGRAM_NAMES['majors'].values()) + list(PROGRAM_NAMES['minors'].values())}"}
        
        if normalized_program in requirements["majors"]:
            progress = check_major_progress(normalized_program, requirements["majors"][normalized_program], normalized_courses)
        elif normalized_program in requirements["minors"]:
            progress = check_minor_progress(normalized_program, requirements["minors"][normalized_program], normalized_courses)
        else:
            return {"error": f"Program '{normalized_program}' not found in requirements"}
        return progress
    
    # Otherwise check all declared programs
    for major in profile.get("majors", []):
        if major in requirements["majors"]:
            progress[major] = check_major_progress(major, requirements["majors"][major], normalized_courses)
    
    for minor in profile.get("minors", []):
        if minor in requirements["minors"]:
            progress[minor] = check_minor_progress(minor, requirements["minors"][minor], normalized_courses)
    
    return progress

def check_major_progress(major: str, req: Dict, normalized_courses: list) -> Dict:
    """Helper function to check progress for a major"""
    # Check required courses
    required_courses = list(req["required_courses"].keys())
    completed_required = [c for c in normalized_courses 
                         if c in required_courses]
    
    # Check math requirements if they exist
    math_progress = None
    completed_math = []
    if "math_requirements" in req:
        math_courses = list(req["math_requirements"].keys())
        elective_slots = sum(1 for course in math_courses if "MATH-ELECTIVE" in course)
        required_math = [course for course in math_courses if "MATH-ELECTIVE" not in course]
        
        # Get valid math electives from requirements
        with open(REQUIREMENTS_FILE, 'r') as f:
            all_requirements = json.load(f)
            valid_math_courses = list(all_requirements["valid_math_electives"].keys())
        
        # First check specifically required math courses
        completed_math = [c for c in normalized_courses if c in required_math]
        
        # Then check for valid math electives
        available_electives = [c for c in normalized_courses 
                             if c in valid_math_courses and c not in completed_math]
        
        # Add up to elective_slots number of valid electives
        completed_math.extend(available_electives[:elective_slots])
        
        math_progress = {
            "completed": len(completed_math),
            "required": len(math_courses),
            "courses": completed_math
        }
    
    # Check electives
    elective_patterns = req["electives"]["valid_patterns"]
    completed_electives = [
        c for c in normalized_courses 
        if matches_pattern(c, elective_patterns) and 
        (not req["electives"]["exclude_required"] or c not in required_courses)
    ]
    
    # Calculate total courses completed and required
    total_completed = (
        len(completed_required) +  # Required courses
        len(completed_math) +      # Math requirements
        min(len(completed_electives), req["electives"]["required_count"])  # Electives
    )
    
    total_required = (
        len(required_courses) +    # Required courses
        (len(req["math_requirements"]) if "math_requirements" in req else 0) +  # Math requirements
        req["electives"]["required_count"]  # Required electives
    )
    
    return {
        "required_courses": {
            "completed": len(completed_required),
            "total": len(required_courses),
            "courses": completed_required
        },
        "electives": {
            "completed": min(len(completed_electives), req["electives"]["required_count"]),
            "required": req["electives"]["required_count"],
            "courses": completed_electives[:req["electives"]["required_count"]]
        },
        "math_requirements": math_progress,
        "total_progress": (total_completed / total_required) * 100
    }

def check_minor_progress(minor: str, req: Dict, normalized_courses: list) -> Dict:
    """Helper function to check progress for a minor"""
    # Check required courses
    required_courses = list(req["required_courses"].keys())
    completed_required = [c for c in normalized_courses 
                         if c in required_courses]
    
    # Check electives if they exist
    electives_progress = None
    total_requirements = len(required_courses)
    completed_count = len(completed_required)
    
    if "electives" in req:
        elective_patterns = req["electives"]["valid_patterns"]
        completed_electives = [
            c for c in normalized_courses 
            if matches_pattern(c, elective_patterns) and 
            (not req["electives"]["exclude_required"] or c not in required_courses)
        ]
        electives_progress = {
            "completed": min(len(completed_electives), req["electives"]["required_count"]),
            "required": req["electives"]["required_count"],
            "courses": completed_electives[:req["electives"]["required_count"]]
        }
        total_requirements += req["electives"]["required_count"]
        completed_count += min(len(completed_electives), req["electives"]["required_count"])
    
    return {
        "required_courses": {
            "completed": len(completed_required),
            "total": len(required_courses),
            "courses": completed_required
        },
        "electives": electives_progress,
        "total_progress": (completed_count / total_requirements) * 100
    } 
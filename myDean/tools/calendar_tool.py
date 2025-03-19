import re
from typing import Dict, List, Optional
from datetime import datetime, time
import json
import os
from langchain.tools import tool
from flask import session

DAY_MAPPING = {
    'monday': 1,
    'tuesday': 2,
    'wednesday': 3,
    'thursday': 4,
    'friday': 5
}

from utils import file_utils as fu

def load_calendar_profile(username: str) -> Dict:
    """Load a user's calendar profile."""
    profile_path = f'data/calendar_profiles/{username}.json'
    default_profile = {
        'courses': [],
        'last_updated': datetime.now().isoformat()
    }
    profile = fu.load_json(profile_path, default_profile)
    # If profile was not found, ensure it is saved for next time
    if profile == default_profile:
        save_calendar_profile(username, profile)
    return profile

def save_calendar_profile(username: str, profile_data: Dict):
    """Save a user's calendar profile."""
    profile_path = f'data/calendar_profiles/{username}.json'
    fu.save_json(profile_path, profile_data)

def parse_meeting_details(meeting_details: str) -> Optional[Dict]:
    """Parse meeting details string into structured format.
    Expected format: "HH:MM AM/PM - HH:MM AM/PM on Day and Day"
    """
    if not meeting_details:
        return None
    
    # Single pattern to match time and days
    pattern = (
        r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*-\s*'  # Start time
        r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s+on\s+'  # End time
        r'((?:Monday|Tuesday|Wednesday|Thursday|Friday)'  # First day
        r'(?:\s+and\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday))*)'  # Additional days
    )
    
    match = re.search(pattern, meeting_details, re.IGNORECASE)
    if not match:
        return None
        
    # Parse times and days
    days = [
        DAY_MAPPING[day.strip()]
        for day in match.group(3).lower().split(' and ')
        if day.strip() in DAY_MAPPING
    ]
    
    if not days:
        return None
    
    return {
        'daysOfWeek': sorted(days),
        'startTime': match.group(1).replace(' ', ''),
        'endTime': match.group(2).replace(' ', ''),
        'schedule': meeting_details
    }

def check_time_conflict(existing_schedule: List[Dict], new_course: Dict) -> bool:
    """Check if a new course conflicts with existing schedule."""
    def parse_time(time_str: str) -> time:
        """Helper function to parse time strings."""
        return datetime.strptime(time_str.replace(' ', ''), '%I:%M%p').time()
    
    new_days = set(new_course['daysOfWeek'])
    new_start = parse_time(new_course['startTime'])
    new_end = parse_time(new_course['endTime'])
    
    return any(
        any(day in new_days for day in course['daysOfWeek'])
        and new_start < parse_time(course['endTime'])
        and new_end > parse_time(course['startTime'])
        for course in existing_schedule
    )

def add_course_to_schedule(course_details: Dict) -> Dict:
    """Add a course to the user's schedule if it doesn't conflict with existing courses."""
    try:
        # Check login and validate input
        username = session.get('username')
        if not username:
            return {'success': False, 'error': 'User not logged in'}

        required_fields = ['title', 'crn', 'instructor', 'schedule']
        if missing := [f for f in required_fields if f not in course_details]:
            return {'success': False, 'error': f'Missing required fields: {", ".join(missing)}'}

        # Load profile and check for duplicates
        profile = load_calendar_profile(username)
        if any(c['crn'] == course_details['crn'] for c in profile['courses']):
            return {'success': False, 'error': f'Course with CRN {course_details["crn"]} already exists'}

        # Parse schedule
        if not (meeting_info := parse_meeting_details(course_details['schedule'])):
            return {'success': False, 'error': 'Invalid course schedule format'}
            
        # Check conflicts
        course_details.update(meeting_info)
        if check_time_conflict(profile['courses'], course_details):
            return {'success': False, 'error': f'Course conflicts with existing schedule'}

        # Add course and save
        profile['last_updated'] = datetime.now().isoformat()
        profile['courses'].append(course_details)
        save_calendar_profile(username, profile)

        return {'success': True, 'message': f'Added {course_details["title"]} to schedule'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def view_schedule() -> Dict:
    """View the current schedule."""
    username = session.get('username')
    if not username:
        return {
            'success': False,
            'error': 'User not logged in'
        }
    
    calendar_profile = load_calendar_profile(username)
    
    if not calendar_profile['courses']:
        return {
            'success': True,
            'message': 'No courses in schedule',
            'courses': []
        }
    
    return {
        'success': True,
        'courses': calendar_profile['courses']
    }

def remove_course_from_schedule(crn: int) -> Dict:
    """Remove a course from the schedule by CRN."""
    username = session.get('username')
    if not username:
        return {'success': False, 'error': 'User not logged in'}
    
    profile = load_calendar_profile(username)
    original_courses = profile['courses']
    profile['courses'] = [c for c in original_courses if c['crn'] != crn]
    
    if len(profile['courses']) == len(original_courses):
        return {'success': False, 'error': f'Course with CRN {crn} not found'}
    
    profile['last_updated'] = datetime.now().isoformat()
    save_calendar_profile(username, profile)
    return {'success': True, 'message': f'Removed course with CRN {crn}'}

def clear_schedule() -> Dict:
    """Remove all courses from the schedule."""
    username = session.get('username')
    if not username:
        return {'success': False, 'error': 'User not logged in'}
    
    profile = load_calendar_profile(username)
    if not profile['courses']:
        return {'success': True, 'message': 'Schedule is already empty'}
    
    course_count = len(profile['courses'])
    profile['courses'] = []
    profile['last_updated'] = datetime.now().isoformat()
    save_calendar_profile(username, profile)
    
    return {'success': True, 'message': f'Removed {course_count} courses from schedule'}

@tool
def calendar_tool(action: str, course_details: Dict = None, crn: int = None) -> Dict:
    """Manage the visual schedule. Can add/remove courses and view the current schedule.
    
    Args:
        action (str): The action to perform: "add", "remove", "view", or "clear"
        course_details (Dict, optional): For "add" action, the course information containing:
            - title: str
            - crn: int
            - instructor: str
            - schedule: str
            - startTime: str
            - endTime: str
        crn (int, optional): The Course Reference Number for remove action
        
    Returns:
        dict: Operation result with success status and relevant data
    """
    if action == "view":
        return view_schedule()
    elif action == "add" and course_details is not None:
        return add_course_to_schedule(course_details)
    elif action == "remove" and crn is not None:
        return remove_course_from_schedule(crn)
    elif action == "clear":
        return clear_schedule()
    else:
        return {
            'success': False,
            'error': 'Invalid action or missing required parameters'
        }

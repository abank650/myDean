from langchain_openai import ChatOpenAI
from tools.transcript_tool import transcript_tool
from tools.course_conversion_tool import normalize_course_numbers
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def process_transcript(file_path):
    """
    Process an academic transcript and return structured course information.
    
    Args:
        file_path (str): Path to the transcript PDF file
        
    Returns:
        dict: Dictionary containing success status, message, and list of courses if successful
    """
    # Initialize the model
    llm = ChatOpenAI(model="gpt-4o")
    
    # Process the transcript
    result = transcript_tool(file_path, llm)
    
    # Format and normalize the courses if successful
    if result['success']:
        # The courses are already formatted with their prefixes (COSC/MATH) in transcript_tool
        courses = result['courses_taken']
        
        # Normalize the courses
        try:
            normalized_courses = normalize_course_numbers(courses)
            result['formatted_courses'] = normalized_courses
            print(f"Normalized courses: {normalized_courses}")
        except Exception as e:
            print(f"Error normalizing courses: {e}")
            # If normalization fails, use the original courses
            result['formatted_courses'] = courses
            print(f"Using original courses: {courses}")
    
    return result
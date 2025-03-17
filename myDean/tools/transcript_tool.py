from langchain_openai import OpenAI
from typing import Dict
import base64
import ast
import io
from langchain_core.messages import HumanMessage
from pdf2image import convert_from_path


def encode_image(image_path: str, is_pdf: bool = False) -> str:
    """
    Convert image or PDF to base64 string
    """
    if is_pdf:
        print("Converting PDF to images...")
        # Convert all pages of PDF to images
        pages = convert_from_path(image_path)
        if not pages:
            raise ValueError("Could not convert PDF to images")
        
        print(f"PDF converted successfully - processing {len(pages)} pages")
        
        # Process each page and combine the results
        all_base64_images = []
        for i, page in enumerate(pages):
            img_byte_arr = io.BytesIO()
            page.save(img_byte_arr, format='JPEG', quality=100)
            img_byte_arr = img_byte_arr.getvalue()
            base64_image = base64.b64encode(img_byte_arr).decode('utf-8')
            all_base64_images.append(base64_image)
        
        return all_base64_images
    else:
        with open(image_path, "rb") as image_file:
            return [base64.b64encode(image_file.read()).decode('utf-8')]

# Tool that processes transcript images/PDFs using the vision-capable LLM
def transcript_tool(file_path: str, llm=OpenAI(model="gpt-4o")) -> Dict:
    """Tool for processing transcript images/PDFs using the vision-capable LLM."""

    try:
        is_pdf = file_path.lower().endswith('.pdf')
        base64_images = encode_image(file_path, is_pdf=is_pdf)
        
        all_courses = []
        for i, base64_image in enumerate(base64_images):
            print(f"Processing page {i+1}/{len(base64_images)}...")
            
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": """Please analyze this academic transcript carefully and:
1. Look for any courses with the subject 'COSC' or 'MATH'
2. Extract ONLY the course numbers (either 3-digit or 4-digit codes)
3. Return them as a Python dictionary with two lists: one for COSC and one for MATH
4. If you find any COSC or MATH courses, make sure to include them in their respective lists

Example format: {'COSC': ['1001', '052', '2011'], 'MATH': ['035', '036', '150']}
Do not include any explanatory text, only return the dictionary."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            )
            
            print("Sending request to model...")
            response = llm.invoke([message])
            raw_response = response.content
            print(f"Raw response from model for page {i+1}: {raw_response}")
            
            try:
                # Clean up the response - remove any markdown code blocks
                cleaned_response = raw_response.replace('```python', '').replace('```', '').strip()
                courses_dict = ast.literal_eval(cleaned_response)
                if not isinstance(courses_dict, dict):
                    raise ValueError("Response is not a dictionary")
                
                # Extend both COSC and MATH courses
                all_courses.extend([f"COSC {num}" for num in courses_dict.get('COSC', [])])
                all_courses.extend([f"MATH {num}" for num in courses_dict.get('MATH', [])])
            except (SyntaxError, ValueError) as e:
                print(f"Failed to parse as dict, trying regex: {e}")
                # Try to extract course numbers using regex if ast.literal_eval fails
                import re
                # Look for course numbers in various formats
                cosc_pattern = r'COSC[- ](\d{3,4})'
                math_pattern = r'MATH[- ](\d{3,4})'
                
                cosc_courses = []
                math_courses = []
                
                # Try to find COSC courses
                cosc_matches = re.findall(cosc_pattern, raw_response, re.IGNORECASE)
                if cosc_matches:
                    cosc_courses = [f"COSC {num}" for num in cosc_matches]
                
                # Try to find MATH courses
                math_matches = re.findall(math_pattern, raw_response, re.IGNORECASE)
                if math_matches:
                    math_courses = [f"MATH {num}" for num in math_matches]
                
                all_courses.extend(cosc_courses)
                all_courses.extend(math_courses)
                
                print(f"Found via regex - COSC: {cosc_courses}, MATH: {math_courses}")
        
        # Remove duplicates while preserving order
        all_courses = list(dict.fromkeys(all_courses))
        
        return {
            "courses_taken": all_courses,
            "success": True,
            "message": f"Found {len(all_courses)} COSC and MATH courses in transcript"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error processing transcript: {str(e)}"
        }
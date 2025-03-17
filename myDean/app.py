import warnings
# Suppress the Pydantic warning message
warnings.filterwarnings('ignore', message='.*pydantic\.error_wrappers.*')

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from myDean import agent
from langchain.schema import HumanMessage
import os
from tools.transcript_executer import process_transcript
from tools.course_conversion_tool import normalize_course_numbers
from datetime import datetime, timedelta
import json
import hashlib
import secrets
import re
from typing import Dict, List, Set
from tools.calendar_tool import remove_course_from_schedule

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a random secret key for sessions
app.permanent_session_lifetime = timedelta(hours=24)  # Session expires after 24 hours

def load_users():
    try:
        with open('data/users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}}

def save_users(users_data):
    with open('data/users.json', 'w') as f:
        json.dump(users_data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_profile(username, profile_data):
    profile_path = f'data/profiles/{username}.json'
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    with open(profile_path, 'w') as f:
        json.dump(profile_data, f, indent=4)

def load_degree_requirements():
    with open('data/degree_requirements.json', 'r') as f:
        return json.load(f)

def check_course_matches_pattern(course: str, patterns: List[str]) -> bool:
    return any(re.match(pattern, course) for pattern in patterns)

def normalize_course_format(course: str) -> str:
    """Normalize course format to use hyphens (e.g., 'COSC 2010' -> 'COSC-2010')"""
    return course.replace(' ', '-')

def calculate_progress(profile: Dict, requirements: Dict) -> Dict:
    completed_courses = set(profile.get('courses_completed', []))
    majors = profile.get('majors', [])
    minors = profile.get('minors', [])
    
    major_name = majors[0] if majors else None
    minor_name = minors[0] if minors else None
    
    result = {
        'major': {'name': major_name, 'requirements': [], 'progress': 0},
        'minor': {'name': minor_name, 'requirements': [], 'progress': 0}
    }
    
    if major_name:
        major_reqs = requirements['majors'].get(major_name, {})
        result['major'] = calculate_program_progress(completed_courses, major_reqs, 'major')
        result['major']['name'] = major_name  # Ensure name is preserved
        
    if minor_name:
        minor_reqs = requirements['minors'].get(minor_name, {})
        result['minor'] = calculate_program_progress(completed_courses, minor_reqs, 'minor')
        result['minor']['name'] = minor_name  # Ensure name is preserved
    
    # Calculate overall progress only from programs that exist
    major_reqs = len(result['major']['requirements']) if major_name else 0
    minor_reqs = len(result['minor']['requirements']) if minor_name else 0
    total_reqs = major_reqs + minor_reqs
    
    if total_reqs > 0:
        major_completed = sum(1 for req in result['major']['requirements'] if req['completed']) if major_name else 0
        minor_completed = sum(1 for req in result['minor']['requirements'] if req['completed']) if minor_name else 0
        result['overall_progress'] = ((major_completed + minor_completed) / total_reqs) * 100
    else:
        result['overall_progress'] = 0
    
    return result

def calculate_program_progress(completed_courses: Set[str], program_reqs: Dict, program_type: str) -> Dict:
    # Normalize all completed courses to use hyphens
    completed_courses = {normalize_course_format(course) for course in completed_courses}
    
    requirements = []
    completed_count = 0
    total_count = 0
    
    # Required courses
    if 'required_courses' in program_reqs:
        for course, desc in program_reqs['required_courses'].items():
            completed = course in completed_courses
            requirements.append({
                'title': desc,
                'details': course,
                'completed': completed
            })
            if completed:
                completed_count += 1
            total_count += 1
    
    # Math requirements
    if 'math_requirements' in program_reqs:
        for course, desc in program_reqs['math_requirements'].items():
            if 'ELECTIVE' in course:
                # Check if any valid math elective is completed
                valid_math_courses = {normalize_course_format(c) for c in load_degree_requirements()['valid_math_electives'].keys()}
                completed = any(c in completed_courses for c in valid_math_courses)
                details = "Any math elective from approved list"
            else:
                completed = course in completed_courses
                details = course
            
            requirements.append({
                'title': desc,
                'details': details,
                'completed': completed
            })
            if completed:
                completed_count += 1
            total_count += 1
    
    # Electives
    if 'electives' in program_reqs:
        elective_req = program_reqs['electives']
        # Get set of required courses to exclude from electives
        required_courses = set()
        if 'required_courses' in program_reqs:
            required_courses.update(program_reqs['required_courses'].keys())
        if 'math_requirements' in program_reqs:
            required_courses.update(course for course in program_reqs['math_requirements'].keys() if 'ELECTIVE' not in course)
        
        # Filter completed courses to only include those that:
        # 1. Match the elective pattern
        # 2. Are not in the required courses list
        completed_electives = [c for c in completed_courses 
                             if check_course_matches_pattern(c, elective_req['valid_patterns']) and
                             normalize_course_format(c) not in required_courses]
        
        requirements.append({
            'title': f"Program Electives",
            'details': f"{len(completed_electives)}/{elective_req['required_count']} {elective_req['description']}",
            'completed': len(completed_electives) >= elective_req['required_count']
        })
        if len(completed_electives) >= elective_req['required_count']:
            completed_count += 1
        total_count += 1
    
    # Additional requirements (for CSES and TES concentration)
    if 'additional_requirements' in program_reqs:
        for req_name, req_details in program_reqs['additional_requirements'].items():
            completed_req = sum(1 for c in completed_courses 
                              if check_course_matches_pattern(c, req_details['valid_patterns']))
            
            requirements.append({
                'title': req_name.replace('_', ' ').title(),
                'details': f"{completed_req}/{req_details['required_count']} {req_details['description']}",
                'completed': completed_req >= req_details['required_count']
            })
            if completed_req >= req_details['required_count']:
                completed_count += 1
            total_count += 1
    
    return {
        'name': program_reqs.get('name', ''),
        'requirements': requirements,
        'progress': (completed_count / total_count * 100) if total_count > 0 else 0
    }

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    users_data = load_users()
    user = users_data['users'].get(username)
    
    if user and user['password'] == hash_password(password):
        session['username'] = username
        return jsonify({'message': 'Login successful'})
    
    return jsonify({'message': 'Invalid username or password'}), 401

@app.route('/onboard', methods=['GET', 'POST'])
def onboard():
    if request.method == 'GET':
        return render_template('onboard.html')
    
    # Handle form submission
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Check if username already exists
    users_data = load_users()
    if username in users_data['users']:
        return jsonify({'message': 'Username already exists'}), 400
    
    # Create user account
    users_data['users'][username] = {
        'password': hash_password(password)
    }
    save_users(users_data)
    
    # Create user profile
    profile_data = {
        'name': request.form.get('name'),
        'grade': request.form.get('grade'),
        'school': request.form.get('school'),
        'majors': [request.form.get('majors')],
        'minors': [request.form.get('minors')] if request.form.get('minors') else [],
        'courses_completed': []
    }
    
    # Handle transcript upload
    if 'transcript' in request.files:
        transcript_file = request.files['transcript']
        if transcript_file.filename:
            # Save transcript temporarily
            temp_path = f"temp/{transcript_file.filename}"
            os.makedirs("temp", exist_ok=True)
            transcript_file.save(temp_path)
            
            # Process transcript
            result = process_transcript(temp_path)
            os.remove(temp_path)
            
            if result['success']:
                # Normalize the courses using course_conversion_tool
                normalized_courses = normalize_course_numbers(result['formatted_courses'])
                profile_data['courses_completed'] = normalized_courses
    
    # Add manually entered courses if any
    manual_courses = request.form.get('courses')
    if manual_courses:
        courses = [c.strip() for c in manual_courses.split(',')]
        # Normalize manually entered courses as well
        normalized_manual_courses = normalize_course_numbers(courses)
        profile_data['courses_completed'].extend(normalized_manual_courses)
    
    # Save profile
    save_profile(username, profile_data)
    
    # Log user in
    session['username'] = username
    return jsonify({'message': 'Account created successfully'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.before_request
def before_request():
    if 'username' not in session and request.endpoint not in ['login', 'onboard', 'static']:
        return redirect(url_for('login'))
    session.permanent = True  # Enable session expiration

@app.route('/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'response': 'Please log in'}), 401
    
    message = request.json.get('message')
    if not message:
        return jsonify({'response': 'No message received'}), 400
    
    try:
        thread_id = session.get('thread_id')
        if not thread_id:
            thread_id = f"thread_{int(datetime.now().timestamp())}"
            session['thread_id'] = thread_id
            print(f"Created new thread_id: {thread_id}")
        else:
            print(f"Using existing thread_id: {thread_id}")
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": session['username']
            }
        }
        stream = agent.stream(
            {"messages": [HumanMessage(content=message)]}, 
            config=config
        )
        
        # Collect all steps and the final response
        steps = []
        final_message = None
        
        for step in stream:
            if 'agent' in step:
                final_message = step['agent']['messages'][0].content
            elif 'thought' in step:
                steps.append(step['thought'])
            
        return jsonify({
            'steps': steps,
            'response': final_message,
            'thread_id': thread_id
        })
        
    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'response': 'Please log in'}), 401
    
    if 'file' not in request.files:
        return jsonify({'response': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'response': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Save the file temporarily
            temp_path = f"temp/{file.filename}"
            os.makedirs("temp", exist_ok=True)
            file.save(temp_path)
            
            # Process the file using our new process_transcript function
            result = process_transcript(temp_path)
            
            # Clean up the temporary file
            os.remove(temp_path)
            
            if result["success"]:
                # Create a message about the courses for the agent
                courses_message = "I've analyzed the transcript and found these courses: " + \
                    ", ".join(result["formatted_courses"]) + \
                    ". Please keep these in mind for future course recommendations."
                
                # Send the courses to the agent like a chat message
                thread_id = session.get('thread_id', f"thread_{int(datetime.now().timestamp())}")
                config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "user_id": session['username']
                    }
                }
                stream = agent.stream(
                    {"messages": [HumanMessage(content=courses_message)]},
                    config=config
                )
                
                # Process the agent's response
                steps = []
                final_message = None
                for step in stream:
                    if 'agent' in step:
                        final_message = step['agent']['messages'][0].content
                    elif 'thought' in step:
                        steps.append(step['thought'])
                
                return jsonify({
                    'steps': steps,
                    'response': final_message or "I've recorded your course history and will use it for recommendations.",
                    'thread_id': thread_id
                })
            else:
                return jsonify({'response': f"Sorry, I couldn't process your transcript. {result['message']}"})
            
        except Exception as e:
            return jsonify({'response': f'Error processing file: {str(e)}'}), 500
    
    return jsonify({'response': 'Invalid file type. Please upload a PDF or image file.'}), 400

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/start_chat', methods=['POST'])
def start_chat():
    if 'username' not in session:
        return jsonify({'message': 'Please log in'}), 401
    
    try:
        # Get user profile
        profile_path = f'data/profiles/{session["username"]}.json'
        with open(profile_path, 'r') as f:
            profile = json.load(f)
        
        # Create context message for the agent
        context_message = f"START_CHAT: The user is {profile['name']}, a {profile['grade']} at {profile['school']} "
        context_message += f"majoring in {profile['majors'][0]}"
        if profile['minors']:
            context_message += f" with a minor in {profile['minors'][0]}"
        context_message += ". They have completed certain courses that are noted in their profile. "
        context_message += "Please greet them, welcome them to signing up for the platform, and offer to help with course planning, degree requirements, and other academic questions."
        
        # Create a new thread for the conversation
        thread_id = f"thread_{int(datetime.now().timestamp())}"
        session['thread_id'] = thread_id
        
        # Get response from agent using stream to match chat endpoint behavior
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": session['username']
            }
        }
        stream = agent.stream(
            {"messages": [HumanMessage(content=context_message)]},
            config=config
        )
        
        # Process the agent's response
        steps = []
        final_message = None
        for step in stream:
            if 'agent' in step:
                final_message = step['agent']['messages'][0].content
            elif 'thought' in step:
                steps.append(step['thought'])
        
        if not final_message:
            print("No response from agent, using fallback")
            final_message = "Hello! I'm here to help you with your course planning and academic questions. What can I assist you with today?"
        
        # Return the agent's response
        return jsonify({
            'steps': steps,
            'response': final_message,
            'thread_id': thread_id,
            'message': 'Chat started successfully'
        })
        
    except Exception as e:
        print(f"Error in start_chat: {str(e)}")
        return jsonify({'error': f'Error starting chat: {str(e)}'}), 500

@app.route('/api/degree-progress')
def get_degree_progress():
    print(f"Getting degree progress for {session['username']}")
    
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        # Load user profile
        profile_path = f'data/profiles/{session["username"]}.json'
        with open(profile_path, 'r') as f:
            profile = json.load(f)
        
        # Load degree requirements
        requirements = load_degree_requirements()
        
        # Calculate progress
        progress = calculate_progress(profile, requirements)
        
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_schedule')
def get_schedule():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        calendar_profile_path = f'data/calendar_profiles/{session["username"]}.json'
        if os.path.exists(calendar_profile_path):
            with open(calendar_profile_path, 'r') as f:
                calendar_data = json.load(f)
                return jsonify(calendar_data)
        else:
            return jsonify({'courses': []})
    except Exception as e:
        print(f"Error loading schedule: {str(e)}")
        return jsonify({'error': 'Failed to load schedule'}), 500

@app.route('/remove_course_direct', methods=['POST'])
def remove_course_direct():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        crn = data.get('crn')
        if not crn:
            return jsonify({'error': 'Missing CRN'}), 400
            
        result = remove_course_from_schedule(crn)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error removing course: {str(e)}")
        return jsonify({'error': 'Failed to remove course'}), 500

if __name__ == '__main__':
    print(f"Server started")
    app.run(debug=True) 
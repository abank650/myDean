const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const charCount = document.getElementById('char-count');
const sendButton = document.getElementById('send-button');
const scrollButton = document.getElementById('scroll-button');
scrollButton.style.display = 'none';
let isUserNearBottom = true;

// Display welcome message if it exists
window.addEventListener('DOMContentLoaded', () => {
    const welcomeMessage = sessionStorage.getItem('welcomeMessage');
    if (welcomeMessage) {
        addMessage(welcomeMessage, false);
        sessionStorage.removeItem('welcomeMessage');  // Clear it after displaying
    }
});

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    
    // Update character count
    const length = this.value.length;
    charCount.textContent = `${length}/1000`;
    
    // Enable/disable send button
    sendButton.disabled = length === 0;
});

// Handle enter key
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendButton.disabled) {
            sendMessage();
        }
    }
});

function toggleInstructions() {
    const panel = document.getElementById('instructions-panel');
    panel.classList.toggle('collapsed');
    const icon = panel.querySelector('.toggle-icon');
    icon.textContent = panel.classList.contains('collapsed') ? '▼' : '▲';
}

function addMessage(message, isUser, isThinking = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'agent-message'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (!isUser) {
        contentDiv.style.paddingLeft = '2rem';
    }

    if (isThinking) {
        contentDiv.innerHTML = '<div class="thinking-indicator"><span>•</span><span>•</span><span>•</span></div>';
        scrollButton.style.display = 'none';
    } else {
        contentDiv.innerHTML = isUser ? message : marked.parse(message);
        
        const hasSignificantOverflow = chatContainer.scrollHeight > (chatContainer.clientHeight + 100);
        if (hasSignificantOverflow) {
            checkIfNearBottom();
        } else {
            scrollButton.style.display = 'none';
        }
    }

    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    if (isUser || isThinking) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    return messageDiv;
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Collapse instructions panel if open
    const panel = document.getElementById('instructions-panel');
    if (!panel.classList.contains('collapsed')) {
        panel.classList.add('collapsed');
        const icon = panel.querySelector('.toggle-icon');
        icon.textContent = '▼';
    }

    addMessage(message, true);
    userInput.value = '';
    userInput.style.height = 'auto';
    charCount.textContent = '0/1000';
    sendButton.disabled = true;

    chatContainer.scrollTop = chatContainer.scrollHeight;
    const thinkingDiv = addMessage(null, false, true);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();
        thinkingDiv.remove();
        addMessage(data.response, false);
        
        // Update both degree progress and schedule after each agent response
        await updateDegreeProgress();
        await loadSchedule();  
        
        // Explicitly check for overflow after response is added
        const hasSignificantOverflow = chatContainer.scrollHeight > (chatContainer.clientHeight + 100);
        if (hasSignificantOverflow && chatContainer.scrollTop < (chatContainer.scrollHeight - chatContainer.clientHeight - 100)) {
            scrollButton.style.display = 'flex';
        }
    } catch (error) {
        thinkingDiv.remove();
        addMessage('Error: Could not get response from the agent.', false);
    }
}

// Check if user is near bottom
function checkIfNearBottom() {
    const threshold = 100;
    const position = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    isUserNearBottom = position < threshold;
    
    const hasSignificantOverflow = chatContainer.scrollHeight > (chatContainer.clientHeight + 100);
    if (hasSignificantOverflow && !isUserNearBottom) {
        scrollButton.style.display = 'flex';
    } else {
        scrollButton.style.display = 'none';
    }
    
    return isUserNearBottom;
}

// Show/hide scroll button based on scroll position
chatContainer.addEventListener('scroll', () => {
    checkIfNearBottom();
    scrollButton.style.display = isUserNearBottom ? 'none' : 'flex';
});

// Scroll to bottom when button is clicked
scrollButton.addEventListener('click', () => {
    chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: 'smooth'
    });
});

// Handle file uploads
document.getElementById('file-upload').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    addMessage(`Uploading transcript: ${file.name}`, true);
    const thinkingDiv = addMessage(null, false, true);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        thinkingDiv.remove();
        addMessage(data.response, false);
    } catch (error) {
        thinkingDiv.remove();
        addMessage('Error: Could not process the file.', false);
    }

    // Reset file input
    this.value = '';
});

function toggleSchedule() {
    const panel = document.getElementById('schedulePanel');
    const scheduleToggle = document.querySelector('.schedule-toggle');
    const progressToggle = document.querySelector('.progress-toggle');
    const container = document.querySelector('.container');
    
    // Collapse instructions panel if it's open
    const instructionsPanel = document.getElementById('instructions-panel');
    if (!instructionsPanel.classList.contains('collapsed')) {
        instructionsPanel.classList.add('collapsed');
        const icon = instructionsPanel.querySelector('.toggle-icon');
        icon.textContent = '▼';
    }
    
    panel.classList.toggle('open');
    scheduleToggle.classList.toggle('open');
    container.classList.toggle('shifted-left');
    
    // Hide/show progress toggle based on schedule panel state
    progressToggle.style.display = panel.classList.contains('open') ? 'none' : 'block';
    
    if (panel.classList.contains('open')) {
        loadSchedule();
    }
}

async function loadSchedule() {
    try {
        const response = await fetch('/get_schedule');
        const data = await response.json();
        if (data.courses) {
            displaySchedule(data.courses);
        }
    } catch (error) {
        console.error('Error loading schedule:', error);
    }
}

function displaySchedule(courses) {
    // Clear existing course blocks
    document.querySelectorAll('.course-block').forEach(block => block.remove());
    
    courses.forEach(course => {
        course.daysOfWeek.forEach(day => {
            const dayIndex = day - 1; // Convert 1-based to 0-based index
            if (dayIndex >= 0 && dayIndex < 5) { // Only process weekdays
                const dayColumn = document.querySelectorAll('.day-slots')[dayIndex];
                
                // Parse times and calculate position
                const [startHour, startMinute] = parseTime(course.startTime);
                const [endHour, endMinute] = parseTime(course.endTime);
                
                // Calculate position relative to 8 AM (start of grid)
                // Each hour is now 50px
                const startPosition = ((startHour - 8) * 50) + Math.floor(startMinute * (50/60));
                const endPosition = ((endHour - 8) * 50) + Math.floor(endMinute * (50/60));
                const duration = endPosition - startPosition;
                
                // Create course block
                const courseBlock = document.createElement('div');
                courseBlock.className = 'course-block';
                courseBlock.style.top = `${startPosition}px`;
                courseBlock.style.height = `${duration}px`;
                courseBlock.title = `${course.title}\n${course.schedule}`;
                
                // Create remove button
                const removeButton = document.createElement('div');
                removeButton.className = 'course-remove';
                removeButton.innerHTML = '×';
                removeButton.title = 'Remove course';
                removeButton.onclick = async (e) => {
                    e.stopPropagation(); // Prevent course block click event
                    if (confirm(`Remove ${course.title.split('(')[0].trim()} from your schedule?`)) {
                        try {
                            const response = await fetch('/remove_course_direct', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ 
                                    crn: course.crn
                                })
                            });
                            
                            const result = await response.json();
                            if (result.success) {
                                // Refresh the schedule immediately
                                await loadSchedule();
                                // Also update degree progress since removing a course might affect it
                                await updateDegreeProgress();
                                
                                // Notify the agent about the course removal
                                await fetch('/chat', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({ 
                                        message: `I've just removed ${course.title} from my schedule using the remove button.`
                                    })
                                });
                            } else {
                                throw new Error(result.error || 'Failed to remove course');
                            }
                        } catch (error) {
                            console.error('Error removing course:', error);
                            alert('Failed to remove course. Please try again.');
                        }
                    }
                };
                
                // Add course content
                const contentDiv = document.createElement('div');
                contentDiv.innerHTML = `
                    <strong>${course.title.split('(')[0].trim()}</strong><br>
                    ${course.instructor.split(',')[0]}
                `;
                
                courseBlock.appendChild(contentDiv);
                courseBlock.appendChild(removeButton);
                dayColumn.appendChild(courseBlock);
            }
        });
    });
}

function parseTime(timeStr) {
    const [time, period] = timeStr.split(/(?=[AP]M)/);
    let [hours, minutes] = time.split(':').map(Number);
    
    if (period === 'PM' && hours !== 12) {
        hours += 12;
    } else if (period === 'AM' && hours === 12) {
        hours = 0;
    }
    
    return [hours, minutes];
}

function toggleProgress() {
    const panel = document.getElementById('progressPanel');
    const progressToggle = document.querySelector('.progress-toggle');
    const scheduleToggle = document.querySelector('.schedule-toggle');
    const container = document.querySelector('.container');
    
    // Collapse instructions panel if it's open
    const instructionsPanel = document.getElementById('instructions-panel');
    if (!instructionsPanel.classList.contains('collapsed')) {
        instructionsPanel.classList.add('collapsed');
        const icon = instructionsPanel.querySelector('.toggle-icon');
        icon.textContent = '▼';
    }
    
    panel.classList.toggle('open');
    progressToggle.classList.toggle('open');
    container.classList.toggle('shifted');
    
    // Hide/show schedule toggle based on progress panel state
    scheduleToggle.style.display = panel.classList.contains('open') ? 'none' : 'block';
    
    // Fetch progress data when opening the panel
    if (panel.classList.contains('open')) {
        fetchAndDisplayProgress();
    }
}

async function fetchAndDisplayProgress() {
    try {
        const response = await fetch('/api/degree-progress');
        const data = await response.json();
        
        if (response.ok) {
            // Update overall progress
            const progressFill = document.querySelector('.progress-fill');
            progressFill.style.width = `${data.overall_progress}%`;
            
            // Update program names in progress summary
            const programNames = document.getElementById('program-names');
            const majorName = data.major.name ? `Major: ${data.major.name}` : '';
            const minorName = data.minor.name ? `Minor: ${data.minor.name}` : '';
            programNames.innerHTML = [majorName, minorName].filter(Boolean).join(' | ');
            
            // Update major requirements
            const majorList = document.getElementById('majorRequirements');
            if (data.major.name) {
                majorList.innerHTML = data.major.requirements.map(req => `
                    <li class="requirement-item ${req.completed ? 'completed' : ''}">
                        <div class="requirement-checkbox">
                            ${req.completed ? '✓' : ''}
                        </div>
                        <div class="requirement-content">
                            <div class="requirement-title">${req.title}</div>
                            <div class="requirement-details">${req.details}</div>
                        </div>
                    </li>
                `).join('');
            } else {
                majorList.innerHTML = '<li>No major selected</li>';
            }
            
            // Update minor requirements
            const minorList = document.getElementById('minorRequirements');
            if (data.minor.name) {
                minorList.innerHTML = data.minor.requirements.map(req => `
                    <li class="requirement-item ${req.completed ? 'completed' : ''}">
                        <div class="requirement-checkbox">
                            ${req.completed ? '✓' : ''}
                        </div>
                        <div class="requirement-content">
                            <div class="requirement-title">${req.title}</div>
                            <div class="requirement-details">${req.details}</div>
                        </div>
                    </li>
                `).join('');
            } else {
                minorList.innerHTML = '<li>No minor selected</li>';
            }
        } else {
            throw new Error(data.error || 'Failed to fetch progress data');
        }
    } catch (error) {
        console.error('Error fetching progress:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.textContent = 'Failed to load degree progress. Please try again later.';
        document.getElementById('progressPanel').prepend(errorMessage);
    }
}

async function updateDegreeProgress() {
    try {
        const response = await fetch('/api/degree-progress');
        const data = await response.json();
        
        if (response.ok) {
            // Update overall progress
            const progressFill = document.querySelector('.progress-fill');
            progressFill.style.width = `${data.overall_progress}%`;
            
            // Update program names in progress summary
            const programNames = document.getElementById('program-names');
            const majorName = data.major.name ? `Major: ${data.major.name}` : '';
            const minorName = data.minor.name ? `Minor: ${data.minor.name}` : '';
            programNames.innerHTML = [majorName, minorName].filter(Boolean).join(' | ');
            
            // Update major requirements
            const majorList = document.getElementById('majorRequirements');
            if (data.major.name) {
                majorList.innerHTML = data.major.requirements.map(req => `
                    <li class="requirement-item ${req.completed ? 'completed' : ''}">
                        <div class="requirement-checkbox">
                            ${req.completed ? '✓' : ''}
                        </div>
                        <div class="requirement-content">
                            <div class="requirement-title">${req.title}</div>
                            <div class="requirement-details">${req.details}</div>
                        </div>
                    </li>
                `).join('');
            } else {
                majorList.innerHTML = '<li>No major selected</li>';
            }
            
            // Update minor requirements
            const minorList = document.getElementById('minorRequirements');
            if (data.minor.name) {
                minorList.innerHTML = data.minor.requirements.map(req => `
                    <li class="requirement-item ${req.completed ? 'completed' : ''}">
                        <div class="requirement-checkbox">
                            ${req.completed ? '✓' : ''}
                        </div>
                        <div class="requirement-content">
                            <div class="requirement-title">${req.title}</div>
                            <div class="requirement-details">${req.details}</div>
                        </div>
                    </li>
                `).join('');
            } else {
                minorList.innerHTML = '<li>No minor selected</li>';
            }
        } else {
            throw new Error(data.error || 'Failed to fetch progress data');
        }
    } catch (error) {
        console.error('Error updating degree progress:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.textContent = 'Failed to update degree progress. Please try again later.';
        document.getElementById('progressPanel').prepend(errorMessage);
    }
}
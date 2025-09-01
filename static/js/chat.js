// Global variables
let currentSessionId = null;
let chatMessages = document.getElementById('chat-messages');
let messageInput = document.getElementById('message-input');
let sendBtn = document.getElementById('send-btn');
let selectedFile = null;

// Voice-related variables
let voiceInputEnabled = false;
let voiceOutputEnabled = false;
let recognition = null;
let speechSynthesis = window.speechSynthesis;
let currentUtterance = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    loadChatSessions();
    updateSystemStatus();
});

// Initialize app
function initializeApp() {
    // Set up event listeners
    messageInput.addEventListener('input', handleInputChange);
    sendBtn.addEventListener('click', () => sendMessage());

    // Auto-resize textarea
    messageInput.addEventListener('input', function() {
        autoResize(this);
    });

    // Handle Enter key
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Check system status periodically
    setInterval(updateSystemStatus, 30000); // Every 30 seconds
}

// Auto-resize textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// Handle input changes
function handleInputChange() {
    const hasContent = messageInput.value.trim().length > 0;
    sendBtn.disabled = !hasContent;
    sendBtn.style.opacity = hasContent ? '1' : '0.5';
}

// Send message
async function sendMessage(message = null) {
    const messageText = message || messageInput.value.trim();

    if (!messageText) return;

    // Show loading state
    showLoading(true);
    sendBtn.disabled = true;

    try {
        // Create user message element
        addMessage(messageText, 'user');

        // Clear input
        messageInput.value = '';
        autoResize(messageInput);
        handleInputChange();

        // Send to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: messageText,
                session_id: currentSessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Update current session
        if (data.session_id && !currentSessionId) {
            currentSessionId = data.session_id;
        }

                    // Add assistant response
            addMessage(data.response, 'assistant', data.metadata, false, data.suggestions, data.message_id);

        // Reload chat sessions
        loadChatSessions();

        // Scroll to bottom
        scrollToBottom();

    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('Sorry, I encountered an error. Please try again.', 'assistant', null, true);
    } finally {
        showLoading(false);
        sendBtn.disabled = false;
    }
}

// Add message to chat
function addMessage(content, role, metadata = null, isError = false, suggestions = null, messageId = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    // Generate unique message ID if not provided
    const uniqueMessageId = messageId || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    messageDiv.setAttribute('data-message-id', uniqueMessageId);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Convert markdown-like formatting to HTML
    const formattedContent = formatMessage(content);
    contentDiv.innerHTML = formattedContent;

    if (metadata) {
        const metadataDiv = document.createElement('div');
        metadataDiv.className = 'message-metadata';

        if (metadata.used_realtime_search) {
            metadataDiv.innerHTML += '<i class="fas fa-search"></i> Searched web ';
        }

        if (metadata.context_sources > 0) {
            metadataDiv.innerHTML += `<i class="fas fa-database"></i> ${metadata.context_sources} sources`;
        }

        contentDiv.appendChild(metadataDiv);
    }

    if (isError) {
        contentDiv.style.borderLeft = '4px solid #ef4444';
    }

    messageDiv.appendChild(contentDiv);

    // Add feedback buttons for assistant messages
    if (role === 'assistant') {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'message-feedback';
        feedbackDiv.innerHTML = `
            <button class="feedback-btn thumbs-up" onclick="giveFeedback('${uniqueMessageId}', 'positive')" title="Good response">
                <i class="fas fa-thumbs-up"></i>
            </button>
            <button class="feedback-btn thumbs-down" onclick="giveFeedback('${uniqueMessageId}', 'negative')" title="Poor response">
                <i class="fas fa-thumbs-down"></i>
            </button>
        `;
        contentDiv.appendChild(feedbackDiv);
    }

    chatMessages.appendChild(messageDiv);

    // Add suggestions as a separate div if available and this is an assistant message
    if (role === 'assistant' && suggestions && suggestions.length > 0) {
        const suggestionsDiv = createSeparateSuggestionsElement(suggestions);
        chatMessages.appendChild(suggestionsDiv);
    }

    // Hide welcome message if this is the first message
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage && chatMessages.children.length > 1) {
        welcomeMessage.style.display = 'none';
    }
}

function createSuggestionsElement(suggestions) {
    const suggestionsDiv = document.createElement('div');
    suggestionsDiv.className = 'message-suggestions';

    const headerDiv = document.createElement('div');
    headerDiv.className = 'suggestions-header';
    headerDiv.innerHTML = '<i class="fas fa-lightbulb"></i> You might also ask:';
    suggestionsDiv.appendChild(headerDiv);

    const suggestionsList = document.createElement('div');
    suggestionsList.className = 'suggestions-list';

    suggestions.forEach((suggestion, index) => {
        const suggestionDiv = document.createElement('div');
        suggestionDiv.className = 'suggestion-item';
        suggestionDiv.innerHTML = `<span class="suggestion-number">${index + 1}</span> ${suggestion}`;
        suggestionDiv.onclick = () => sendMessage(suggestion);
        suggestionDiv.title = 'Click to ask this question';
        suggestionsList.appendChild(suggestionDiv);
    });

    suggestionsDiv.appendChild(suggestionsList);
    return suggestionsDiv;
}

function createSeparateSuggestionsElement(suggestions) {
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'separate-suggestions-container';

    const suggestionsDiv = document.createElement('div');
    suggestionsDiv.className = 'separate-suggestions';

    const headerDiv = document.createElement('div');
    headerDiv.className = 'suggestions-header';
    headerDiv.innerHTML = '<i class="fas fa-lightbulb"></i> Suggestions:';
    suggestionsDiv.appendChild(headerDiv);

    const suggestionsList = document.createElement('div');
    suggestionsList.className = 'suggestions-list';

    suggestions.forEach((suggestion, index) => {
        const suggestionDiv = document.createElement('div');
        suggestionDiv.className = 'separate-suggestion-item';
        suggestionDiv.innerHTML = `<span class="suggestion-number">${index + 1}</span> ${suggestion}`;
        suggestionDiv.onclick = () => sendMessage(suggestion);
        suggestionDiv.title = 'Click to ask this question';
        suggestionsList.appendChild(suggestionDiv);
    });

    suggestionsDiv.appendChild(suggestionsList);
    suggestionsContainer.appendChild(suggestionsDiv);

    return suggestionsContainer;
}

// Format message content (basic markdown)
function formatMessage(content) {
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

// Scroll to bottom of chat
function scrollToBottom() {
    // Use setTimeout to ensure DOM is updated before scrolling
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
}

// Load chat sessions
async function loadChatSessions() {
    try {
        const response = await fetch('/api/sessions');
        const data = await response.json();

        const chatList = document.getElementById('chat-list');
        chatList.innerHTML = '';

        if (data.sessions.length === 0) {
            chatList.innerHTML = '<div class="no-chats">No chat history yet</div>';
            return;
        }

        data.sessions.forEach(session => {
            const sessionDiv = document.createElement('div');
            sessionDiv.className = `chat-item ${session.session_id === currentSessionId ? 'active' : ''}`;
            sessionDiv.onclick = () => loadSession(session.session_id);

            sessionDiv.innerHTML = `
                <div class="chat-item-content">
                    <div class="chat-item-title">${session.title}</div>
                    <div class="chat-item-meta">
                        ${session.message_count} messages • ${formatDate(session.updated_at)}
                    </div>
                </div>
            `;

            chatList.appendChild(sessionDiv);
        });
    } catch (error) {
        console.error('Error loading chat sessions:', error);
    }
}

// Load specific session
async function loadSession(sessionId) {
    try {
        const response = await fetch(`/api/session/${sessionId}`);
        const data = await response.json();

        currentSessionId = sessionId;

        // Clear current messages
        chatMessages.innerHTML = '';

        // Add messages
        data.messages.forEach(msg => {
            addMessage(msg.content, msg.role, msg.metadata, false, msg.suggestions);
        });

        // Update active session in sidebar
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.closest('.chat-item').classList.add('active');

        // Scroll to bottom
        scrollToBottom();
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

// Start new chat
function startNewChat() {
    currentSessionId = null;

    // Clear messages and show welcome
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-content">
                <img src="/img/beeonix.png" alt="AI Assistant" class="welcome-avatar">
                <h2>Welcome to Regulatory FAQ Assistant</h2>
                <p>I'm here to help you understand banking regulations and compliance requirements.</p>
            </div>
        </div>
        <div class="separate-suggestions-container">
            <div class="separate-suggestions">
                <div class="suggestions-header">
                    <i class="fas fa-lightbulb"></i> Try asking:
                </div>
                <div class="suggestions-list">
                    <div class="separate-suggestion-item" onclick="sendMessage('What are the new requirements for digital banking accounts?')">
                        <span class="suggestion-number">1</span> What are the new requirements for digital banking accounts?
                    </div>
                    <div class="separate-suggestion-item" onclick="sendMessage('When do these regulatory changes take effect?')">
                        <span class="suggestion-number">2</span> When do these regulatory changes take effect?
                    </div>
                    <div class="separate-suggestion-item" onclick="sendMessage('How will this affect my current banking transactions?')">
                        <span class="suggestion-number">3</span> How will this affect my current banking transactions?
                    </div>
                </div>
            </div>
        </div>
    `;

    // Update sidebar
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });

    // Clear input
    messageInput.value = '';
    messageInput.focus();
}

// Update system status
async function updateSystemStatus() {
    try {
        const response = await fetch('/api/system-status');
        const data = await response.json();

        const statusElement = document.getElementById('system-status');
        const indicator = statusElement.querySelector('.status-indicator');

        indicator.className = 'status-indicator';

        if (data.status === 'ready') {
            indicator.classList.add('status-ready');
            statusElement.querySelector('span').textContent = 'System Ready';
        } else if (data.status === 'initializing') {
            indicator.classList.add('status-initializing');
            statusElement.querySelector('span').textContent = 'Initializing...';
        } else {
            indicator.classList.add('status-error');
            statusElement.querySelector('span').textContent = 'System Error';
        }
    } catch (error) {
        console.error('Error updating system status:', error);
    }
}

// Handle key press in input
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) {
        return 'Today';
    } else if (diffDays === 2) {
        return 'Yesterday';
    } else if (diffDays <= 7) {
        return `${diffDays - 1} days ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// Show/hide loading overlay
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = show ? 'block' : 'none';
}

// Modal functions for regulation processing
function showRegulationModal() {
    document.getElementById('regulation-modal').style.display = 'block';
}

function closeRegulationModal() {
    document.getElementById('regulation-modal').style.display = 'none';
    // Clear form
    document.getElementById('regulatory-text').value = '';
    document.getElementById('context').value = '';
    // Clear selected file
    removeFile();
}

// Process regulation
async function processRegulation() {
    const regulatoryText = document.getElementById('regulatory-text').value.trim();
    const context = document.getElementById('context').value.trim();

    // Validate that either text or file is provided
    if (!regulatoryText && !selectedFile) {
        alert('Please enter regulatory text or upload a PDF file');
        return;
    }

    showLoading(true);

    try {
        let response;

        if (selectedFile) {
            // Handle PDF upload
            const formData = new FormData();
            formData.append('pdf_file', selectedFile);
            if (regulatoryText) {
                formData.append('regulatory_text', regulatoryText);
            }
            if (context) {
                formData.append('context', context);
            }

            response = await fetch('/api/process-regulation', {
                method: 'POST',
                body: formData
            });
        } else {
            // Handle text only
            response = await fetch('/api/process-regulation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    regulatory_text: regulatoryText,
                    context: context
                })
            });
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Show success message
        alert(data.message);

        // Close modal and reset
        closeRegulationModal();

        // Update system status
        updateSystemStatus();

    } catch (error) {
        console.error('Error processing regulation:', error);
        alert('Error processing regulation. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('regulation-modal');
    if (event.target === modal) {
        closeRegulationModal();
    }
}

// File Upload Functions
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        validateAndSetFile(file);
    }
}

function validateAndSetFile(file) {
    // Validate file type
    if (file.type !== 'application/pdf') {
        alert('Please select a PDF file only.');
        return;
    }

    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024; // 10MB in bytes
    if (file.size > maxSize) {
        alert('File size must be less than 10MB.');
        return;
    }

    selectedFile = file;
    updateFileDisplay();
}

function updateFileDisplay() {
    const uploadArea = document.getElementById('file-upload-area');
    const uploadPlaceholder = uploadArea.querySelector('.upload-placeholder');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');

    if (selectedFile) {
        uploadPlaceholder.style.display = 'none';
        fileInfo.style.display = 'block';
        fileName.textContent = selectedFile.name;
        fileSize.textContent = formatFileSize(selectedFile.size);
    } else {
        uploadPlaceholder.style.display = 'block';
        fileInfo.style.display = 'none';
    }
}

function removeFile() {
    selectedFile = null;
    document.getElementById('pdf-file').value = '';
    updateFileDisplay();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Drag and Drop Functionality
document.addEventListener('DOMContentLoaded', function() {
    const uploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('pdf-file');

    if (uploadArea) {
        // Click to open file dialog
        uploadArea.addEventListener('click', function() {
            fileInput.click();
        });

        // Drag and drop events
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                validateAndSetFile(files[0]);
            }
        });
    }
});

// Voice Input Functions
function toggleVoiceInput() {
    const voiceBtn = document.getElementById('voice-input-btn');

    if (!voiceInputEnabled) {
        startVoiceInput();
    } else {
        stopVoiceInput();
    }
}

function startVoiceInput() {
    // Check if browser supports speech recognition
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
        return;
    }

    try {
        // Initialize speech recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();

        // Configure recognition
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        // Event handlers
        recognition.onstart = function() {
            voiceInputEnabled = true;
            const voiceBtn = document.getElementById('voice-input-btn');
            voiceBtn.classList.add('active');

            // Show voice status
            const voiceStatus = document.getElementById('voice-input-status');
            const statusText = document.getElementById('voice-status-text');
            voiceStatus.style.display = 'flex';
            statusText.textContent = 'Listening...';
        };

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            messageInput.value = transcript;
            autoResize(messageInput);
            handleInputChange();

            // Automatically send the message if it's a complete sentence
            if (transcript.trim().endsWith('.') || transcript.trim().endsWith('?') || transcript.trim().endsWith('!')) {
                // Hide the voice status when auto-sending
                setTimeout(() => {
                    const voiceStatus = document.getElementById('voice-input-status');
                    if (voiceStatus) voiceStatus.style.display = 'none';
                    sendVoiceMessage(transcript.trim());
                }, 1500); // Give user time to see the transcript
            }
        };

        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            const statusText = document.getElementById('voice-status-text');
            statusText.textContent = `Error: ${event.error}`;
            setTimeout(() => stopVoiceInput(), 2000);
        };

        recognition.onend = function() {
            stopVoiceInput();
        };

        // Start recognition
        recognition.start();

    } catch (error) {
        console.error('Error starting voice input:', error);
        alert('Failed to start voice input. Please try again.');
    }
}

function stopVoiceInput() {
    if (recognition) {
        recognition.stop();
    }

    voiceInputEnabled = false;
    const voiceBtn = document.getElementById('voice-input-btn');
    voiceBtn.classList.remove('active');

    // Hide voice status
    const voiceStatus = document.getElementById('voice-input-status');
    voiceStatus.style.display = 'none';
}

// Voice Output Functions
function toggleVoiceOutput() {
    const voiceBtn = document.getElementById('voice-output-btn');

    if (!voiceOutputEnabled) {
        voiceOutputEnabled = true;
        voiceBtn.classList.add('active');
        showNotification('Voice output enabled', 'success');
    } else {
        voiceOutputEnabled = false;
        voiceBtn.classList.remove('active');
        stopCurrentSpeech();
        showNotification('Voice output disabled', 'info');
    }

    // Save preference to localStorage
    localStorage.setItem('voiceOutputEnabled', voiceOutputEnabled);
}

function speakText(text, callback = null) {
    if (!voiceOutputEnabled || !speechSynthesis) {
        if (callback) callback();
        return;
    }

    // Stop any current speech
    stopCurrentSpeech();

    // Create utterance
    currentUtterance = new SpeechSynthesisUtterance(text);

    // Configure voice settings
    currentUtterance.rate = 0.9; // Slightly slower for clarity
    currentUtterance.pitch = 1;
    currentUtterance.volume = 0.8;

    // Set voice (prefer female voice for better user experience)
    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice =>
        voice.name.toLowerCase().includes('female') ||
        voice.name.toLowerCase().includes('samantha') ||
        voice.name.toLowerCase().includes('alex')
    );
    if (preferredVoice) {
        currentUtterance.voice = preferredVoice;
    }

    // Event handlers
    currentUtterance.onstart = function() {
        const voiceBtn = document.getElementById('voice-output-btn');
        voiceBtn.style.animation = 'speaking 1s infinite';
    };

    currentUtterance.onend = function() {
        const voiceBtn = document.getElementById('voice-output-btn');
        voiceBtn.style.animation = '';
        if (callback) callback();
    };

    currentUtterance.onerror = function(event) {
        console.error('Speech synthesis error:', event);
        const voiceBtn = document.getElementById('voice-output-btn');
        voiceBtn.style.animation = '';
        if (callback) callback();
    };

    // Start speaking
    speechSynthesis.speak(currentUtterance);
}

function stopCurrentSpeech() {
    if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
    }
    if (currentUtterance) {
        currentUtterance = null;
    }
    const voiceBtn = document.getElementById('voice-output-btn');
    voiceBtn.style.animation = '';
}

// Enhanced sendMessage function with voice output
function sendVoiceMessage(message = null) {
    const messageText = message || messageInput.value.trim();

    if (!messageText) return;

    // Show loading state
    showLoading(true);
    sendBtn.disabled = true;

    try {
        // Create user message element
        addMessage(messageText, 'user');

        // Clear input
        messageInput.value = '';
        autoResize(messageInput);
        handleInputChange();

        // Send to voice query endpoint
        const response = fetch('/api/voice_query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: messageText,
                session_id: currentSessionId
            })
        });

        response.then(async (res) => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

                    const data = await res.json();

        // Update current session
        if (data.session_id && !currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Add assistant response
        addMessage(data.response, 'assistant', data.metadata, false, data.suggestions, data.message_id);

        // Speak the response if voice output is enabled
        if (voiceOutputEnabled) {
            speakText(data.response);
        }

        // Reload chat sessions
        loadChatSessions();

        // Scroll to bottom
        scrollToBottom();

        }).catch((error) => {
            console.error('Error sending voice message:', error);
            const errorMsg = 'Sorry, I encountered an error. Please try again.';
            addMessage(errorMsg, 'assistant', null, true);

            if (voiceOutputEnabled) {
                speakText(errorMsg);
            }
        }).finally(() => {
            showLoading(false);
            sendBtn.disabled = false;
        });

    } catch (error) {
        console.error('Error sending voice message:', error);
        addMessage('Sorry, I encountered an error. Please try again.', 'assistant', null, true);
        showLoading(false);
        sendBtn.disabled = false;
    }
}

// Notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas ${getNotificationIcon(type)}"></i>
        <span>${message}</span>
    `;

    // Add to page
    document.body.appendChild(notification);

    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // Hide after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

function getNotificationIcon(type) {
    switch (type) {
        case 'success': return 'fa-check-circle';
        case 'error': return 'fa-exclamation-circle';
        case 'warning': return 'fa-exclamation-triangle';
        default: return 'fa-info-circle';
    }
}

// Initialize voice settings on load
document.addEventListener('DOMContentLoaded', function() {
    // Load voice output preference
    const savedVoiceOutput = localStorage.getItem('voiceOutputEnabled');
    if (savedVoiceOutput === 'true') {
        voiceOutputEnabled = true;
        const voiceBtn = document.getElementById('voice-output-btn');
        voiceBtn.classList.add('active');
    }

    // Ensure voices are loaded
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = function() {
            console.log('Voices loaded:', speechSynthesis.getVoices().length);
        };
    }
});

// Auto-focus input on load
window.addEventListener('load', function() {
    messageInput.focus();
});

// Feedback functionality
async function giveFeedback(messageId, feedbackType) {
    try {
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        const feedbackButtons = messageDiv.querySelectorAll('.feedback-btn');

        // Visual feedback
        feedbackButtons.forEach(btn => btn.classList.remove('selected'));
        const clickedBtn = messageDiv.querySelector(`.thumbs-${feedbackType === 'positive' ? 'up' : 'down'}`);
        clickedBtn.classList.add('selected');

        // Send feedback to server
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message_id: messageId,
                feedback_type: feedbackType,
                session_id: currentSessionId,
                timestamp: new Date().toISOString()
            })
        });

        if (response.ok) {
            // Show success feedback
            showToast('Thank you for your feedback!', 'success');
        } else {
            console.error('Failed to submit feedback');
            showToast('Failed to submit feedback', 'error');
        }
    } catch (error) {
        console.error('Error submitting feedback:', error);
        showToast('Error submitting feedback', 'error');
    }
}

// Analytics modal functions
function showAnalyticsModal() {
    const modal = document.getElementById('analytics-modal');
    modal.style.display = 'block';
    loadAnalyticsData();
}

function closeAnalyticsModal() {
    const modal = document.getElementById('analytics-modal');
    modal.style.display = 'none';
}

async function loadAnalyticsData() {
    try {
        const response = await fetch('/api/analytics');
        const data = await response.json();

        // Update summary cards
        document.getElementById('positive-count').textContent = data.positive_count || 0;
        document.getElementById('negative-count').textContent = data.negative_count || 0;
        document.getElementById('total-feedback').textContent = data.total_feedback || 0;

        // Update recent feedback list
        const feedbackList = document.getElementById('recent-feedback-list');
        feedbackList.innerHTML = '';

        if (data.recent_feedback && data.recent_feedback.length > 0) {
            data.recent_feedback.forEach(feedback => {
                const feedbackItem = document.createElement('div');
                feedbackItem.className = 'feedback-item';
                feedbackItem.innerHTML = `
                    <div class="feedback-type ${feedback.feedback_type}">
                        <i class="fas fa-thumbs-${feedback.feedback_type === 'positive' ? 'up' : 'down'}"></i>
                    </div>
                    <div class="feedback-content">
                        <p>${feedback.query || 'N/A'}</p>
                        <small>${new Date(feedback.timestamp).toLocaleString()}</small>
                    </div>
                `;
                feedbackList.appendChild(feedbackItem);
            });
        } else {
            feedbackList.innerHTML = '<p class="no-feedback">No feedback available yet.</p>';
        }

        // Update chart if Chart.js is available
        if (typeof Chart !== 'undefined' && data.chart_data) {
            updateFeedbackChart(data.chart_data);
        }

    } catch (error) {
        console.error('Error loading analytics data:', error);
        showToast('Failed to load analytics data', 'error');
    }
}

function updateFeedbackChart(chartData) {
    const ctx = document.getElementById('feedback-chart').getContext('2d');

    // Destroy existing chart if it exists
    if (window.feedbackChart) {
        window.feedbackChart.destroy();
    }

    window.feedbackChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Positive Feedback',
                data: chartData.positive,
                borderColor: 'var(--primary-blue)',
                backgroundColor: 'rgba(14, 165, 233, 0.1)',
                tension: 0.4
            }, {
                label: 'Negative Feedback',
                data: chartData.negative,
                borderColor: 'var(--violet)',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Feedback Trends Over Time'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

async function exportAnalytics() {
    try {
        const response = await fetch('/api/analytics/export');
        const data = await response.json();

        // Create CSV content
        let csvContent = 'Date,Query,Feedback Type,Session ID\n';
        data.feedback.forEach(item => {
            csvContent += `${item.timestamp},${item.query || ''},${item.feedback_type},${item.session_id}\n`;
        });

        // Download CSV
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `feedback_analytics_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Analytics report exported successfully!', 'success');
    } catch (error) {
        console.error('Error exporting analytics:', error);
        showToast('Failed to export analytics', 'error');
    }
}

// Toast notification function
function showToast(message, type = 'info') {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Show toast
    setTimeout(() => toast.classList.add('show'), 100);

    // Hide toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Download current chat session as PDF
async function downloadCurrentChat() {
    if (!currentSessionId) {
        showToast('Please start a conversation first', 'error');
        return;
    }

    // Show loading state
    const downloadBtn = document.getElementById('download-chat-btn');
    const originalIcon = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    downloadBtn.disabled = true;

    try {
        const response = await fetch(`/api/download-chat/${currentSessionId}`);
        if (!response.ok) {
            throw new Error('Failed to download chat');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `regulatory_faq_chat_${new Date().toISOString().split('T')[0]}_${currentSessionId.slice(-6)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Chat downloaded successfully!', 'success');
    } catch (error) {
        console.error('Error downloading chat:', error);
        showToast('Failed to download chat', 'error');
    } finally {
        // Restore button state
        downloadBtn.innerHTML = originalIcon;
        downloadBtn.disabled = false;
    }
}

// Download specific chat as PDF (legacy function for compatibility)
async function downloadChatPDF(sessionId) {
    try {
        const response = await fetch(`/api/download-chat/${sessionId}`);
        if (!response.ok) {
            throw new Error('Failed to download chat');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_session_${sessionId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Chat downloaded successfully!', 'success');
    } catch (error) {
        console.error('Error downloading chat:', error);
        showToast('Failed to download chat', 'error');
    }
}

// Initialize analytics modal close handler
document.addEventListener('DOMContentLoaded', function() {
    // Close modal when clicking outside
    window.onclick = function(event) {
        const analyticsModal = document.getElementById('analytics-modal');
        const regulationModal = document.getElementById('regulation-modal');

        if (event.target === analyticsModal) {
            closeAnalyticsModal();
        }
        if (event.target === regulationModal) {
            closeRegulationModal();
        }
    };
});

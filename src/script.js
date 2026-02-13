/* ============================================
   VALH - MINIMALISTIC NEURAL ASSISTANT
   Focus: Tool execution tracking with natural UX
   ============================================ */

// ============================================
// STATE MANAGEMENT
// EXTENSION POINT: Add more state properties
// ============================================

const AppState = {
    // Connection state
    state: 'IDLE', // 'IDLE' | 'THINKING' | 'WORKING'
    connected: false,
    
    // Metrics
    metrics: {
        total: 0,
        success: 0,
        error: 0
    },
    
    // Tool executions
    executions: [], // Array of execution objects
    
    // Current streaming message
    currentAssistantMessage: null
};

// ============================================
// DOM ELEMENTS
// ============================================

const DOM = {
    // Tools panel
    toolsTimeline: document.getElementById('tools-timeline'),
    totalOps: document.getElementById('total-ops'),
    successOps: document.getElementById('success-ops'),
    errorOps: document.getElementById('error-ops'),
    clearBtn: document.getElementById('clear-tools'),
    
    // Conversation
    messages: document.getElementById('messages'),
    messagesContainer: document.getElementById('messages-container'),
    userInput: document.getElementById('user-input'),
    sendBtn: document.getElementById('send-btn'),
    
    // Status
    statusText: document.getElementById('status-text'),
    
    // Mascot - EXTENSION POINT: Add more mascot elements
    mascot: document.getElementById('mascot'),
    pupils: document.querySelectorAll('.pupil')
};

// ============================================
// WEBSOCKET CONNECTION
// EXTENSION POINT: Add reconnection limits, ping/pong
// ============================================

class WebSocketConnection {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnects = 5;
        this.reconnectDelay = 3000;
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws`;
        
        this.socket = new WebSocket(url);
        
        this.socket.onopen = () => {
            console.log('✓ Connected');
            AppState.connected = true;
            this.reconnectAttempts = 0;
            updateState('IDLE');
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Failed to parse message:', error);
            }
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.socket.onclose = () => {
            console.log('✗ Disconnected');
            AppState.connected = false;
            this.attemptReconnect();
        };
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnects) {
            this.reconnectAttempts++;
            DOM.statusText.textContent = `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnects})`;
            setTimeout(() => this.connect(), this.reconnectDelay);
        } else {
            DOM.statusText.textContent = 'Connection lost';
        }
    }
    
    /* ============================================
       MESSAGE HANDLING
       EXTENSION POINT: Add more message types
       ============================================ */
    handleMessage(data) {
        switch(data.type) {
            case 'status':
                // Global state change
                updateState(data.status.toUpperCase());
                break;
                
            case 'chat_message':
                // Streaming or final chat messages
                this.handleChatMessage(data.payload);
                break;
                
            case 'tool_execution_started':
                // Tool execution begins
                updateState('WORKING');
                addToolExecution(data.payload);
                break;
                
            case 'tool_execution_completed':
                // Tool execution succeeds
                updateToolExecution(data.payload, 'success');
                setTimeout(() => {
                    if (AppState.state === 'WORKING') updateState('IDLE');
                }, 800);
                break;
                
            case 'tool_execution_error':
                // Tool execution fails
                updateToolExecution(data.payload, 'error');
                setTimeout(() => {
                    if (AppState.state === 'WORKING') updateState('IDLE');
                }, 800);
                break;
                
            // EXTENSION POINT: Add more message types
            // case 'file_upload':
            // case 'code_execution':
        }
    }
    
    handleChatMessage(payload) {
        if (payload.role === 'assistant') {
            // Update state based on streaming
            if (!payload.final) {
                updateState('THINKING');
            } else {
                updateState('IDLE');
            }
            
            // Create or update message
            if (!AppState.currentAssistantMessage) {
                addMessage('assistant', payload.content);
                AppState.currentAssistantMessage = DOM.messages.lastElementChild;
            } else {
                const content = AppState.currentAssistantMessage.querySelector('.msg-content');
                content.innerHTML = formatMessage(payload.content);
            }
            
            // Clear reference if final
            if (payload.final) {
                AppState.currentAssistantMessage = null;
            }
        } else if (payload.role === 'user') {
            addMessage('user', payload.content);
        }
        
        scrollToBottom();
    }
}

// ============================================
// STATE UPDATES
// EXTENSION POINT: Add custom state behaviors
// ============================================

function updateState(newState) {
    AppState.state = newState;
    document.body.setAttribute('data-state', newState);
    
    // Update status text
    const statusLabels = {
        'IDLE': 'Listening',
        'THINKING': 'Thinking',
        'WORKING': 'Working'
    };
    DOM.statusText.textContent = statusLabels[newState] || newState;
    
    // EXTENSION POINT: Trigger custom animations or sounds
    // playStateSound(newState);
    // updateBackgroundColor(newState);
}

// ============================================
// NATURAL MASCOT BEHAVIORS
// EXTENSION POINT: Add more lifelike behaviors
// ============================================

class MascotBehaviors {
    constructor() {
        this.lookAroundInterval = null;
        this.init();
    }
    
    init() {
        // Natural idle behavior - occasionally look around
        this.startIdleBehavior();
    }
    
    startIdleBehavior() {
        // EXTENSION POINT: Add more idle animations
        // - Random eye direction changes
        // - Occasional surprised look
        // - Yawn animation after period of inactivity
        
        this.lookAroundInterval = setInterval(() => {
            if (AppState.state === 'IDLE') {
                this.randomLook();
            }
        }, 5000); // Look around every 5 seconds when idle
    }
    
    randomLook() {
        // Make pupils look in random direction
        const directions = [
            { x: 1, y: 1 },   // bottom right
            { x: 3, y: 1 },   // top right
            { x: 1, y: 3 },   // bottom left
            { x: 3, y: 3 },   // top left
            { x: 2, y: 2 }    // center
        ];
        
        const direction = directions[Math.floor(Math.random() * directions.length)];
        
        DOM.pupils.forEach(pupil => {
            pupil.style.transform = `translate(${direction.x}px, ${direction.y}px)`;
        });
        
        // Return to center after a moment
        setTimeout(() => {
            DOM.pupils.forEach(pupil => {
                pupil.style.transform = 'translate(2px, 2px)';
            });
        }, 1500);
    }
    
    // EXTENSION POINT: Add more behaviors
    // surprised() { ... }
    // happy() { ... }
    // confused() { ... }
}

// ============================================
// TOOL EXECUTION TRACKING
// ============================================

function addToolExecution(payload) {
    // Remove empty state if present
    const emptyState = DOM.toolsTimeline.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    // Create execution object
    const execution = {
        id: generateId(),
        tool: payload.tool_name,
        args: payload.arguments || {},
        startTime: Date.now(),
        endTime: null,
        duration: null,
        status: 'active',
        result: null
    };
    
    AppState.executions.push(execution);
    AppState.metrics.total++;
    updateMetrics();
    
    // Create and add card
    const card = createToolCard(execution);
    DOM.toolsTimeline.appendChild(card);
    scrollTools();
}

function updateToolExecution(payload, status) {
    // Find the active execution for this tool
    const execution = AppState.executions.find(
        e => e.tool === payload.tool_name && e.status === 'active'
    );
    
    if (!execution) return;
    
    // Update execution data
    execution.endTime = Date.now();
    execution.duration = execution.endTime - execution.startTime;
    execution.status = status;
    execution.result = payload.result || payload.error;
    
    // Update metrics
    if (status === 'success') {
        AppState.metrics.success++;
    } else if (status === 'error') {
        AppState.metrics.error++;
    }
    updateMetrics();
    
    // Update card in DOM
    const card = document.getElementById(execution.id);
    if (card) {
        card.className = `tool-card ${status}`;
        
        // Add duration
        const header = card.querySelector('.tool-header');
        const durationSpan = document.createElement('span');
        durationSpan.className = 'tool-duration';
        durationSpan.textContent = `${execution.duration}ms`;
        header.appendChild(durationSpan);
        
        // Add or update result section
        let resultSection = card.querySelector('.detail-section:last-child');
        if (!resultSection || !resultSection.textContent.includes('RESULT')) {
            resultSection = createDetailSection('Result', execution.result);
            card.querySelector('.tool-details').appendChild(resultSection);
        }
    }
}

/* ============================================
   TOOL CARD CREATION
   EXTENSION POINT: Customize card appearance
   ============================================ */
function createToolCard(execution) {
    const card = document.createElement('div');
    card.className = `tool-card ${execution.status}`;
    card.id = execution.id;
    
    const time = new Date(execution.startTime).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
    
    // Tool icon based on name - EXTENSION POINT: Add more icons
    const icon = getToolIcon(execution.tool);
    
    card.innerHTML = `
        <div class="tool-header">
            <div class="tool-info">
                <div class="tool-name">${icon} ${execution.tool}</div>
                <div class="tool-time">${time}</div>
            </div>
            <svg class="expand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </div>
        <div class="tool-details">
            ${createDetailSection('Arguments', execution.args).outerHTML}
        </div>
    `;
    
    // Toggle expand on click
    const header = card.querySelector('.tool-header');
    header.addEventListener('click', () => {
        card.classList.toggle('expanded');
    });
    
    return card;
}

function createDetailSection(label, content) {
    const section = document.createElement('div');
    section.className = 'detail-section';
    
    const formattedContent = typeof content === 'string' 
        ? content 
        : JSON.stringify(content, null, 2);
    
    // Truncate if too long - EXTENSION POINT: Add "show more" button
    const truncated = formattedContent.length > 500 
        ? formattedContent.substring(0, 500) + '\n... [truncated]'
        : formattedContent;
    
    section.innerHTML = `
        <span class="detail-label">${label}</span>
        <div class="detail-content">${truncated}</div>
    `;
    
    return section;
}

/* ============================================
   TOOL ICONS - EXTENSION POINT: Add more
   ============================================ */
function getToolIcon(toolName) {
    const icons = {
        'list_directory': '📁',
        'read_file': '📄',
        'write_file': '✏️',
        'run_command': '⚡',
        'bash': '💻',
        'python': '🐍',
        'search': '🔍',
        'git': '🔧',
        'web_search': '🌐',
        'api_call': '🔌',
        'database': '🗄️'
    };
    
    return icons[toolName] || '⚙️';
}

// ============================================
// MESSAGE HANDLING
// ============================================

function addMessage(role, content) {
    const msg = document.createElement('div');
    msg.className = `msg-${role}`;
    
    if (role === 'system') {
        msg.className = 'system-msg';
        msg.textContent = content;
    } else {
        msg.innerHTML = `<div class="msg-content">${formatMessage(content)}</div>`;
    }
    
    DOM.messages.appendChild(msg);
    scrollToBottom();
}

/* ============================================
   MESSAGE FORMATTING
   EXTENSION POINT: Add more markdown support
   - Lists (ordered/unordered)
   - Headings
   - Links
   - Images
   ============================================ */
function formatMessage(text) {
    if (!text) return '<span style="opacity: 0.5">...</span>';
    
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // **bold**
        .replace(/`([^`]+)`/g, '<code>$1</code>');          // `code`
}

// ============================================
// UI HELPERS
// ============================================

function updateMetrics() {
    DOM.totalOps.textContent = AppState.metrics.total;
    DOM.successOps.textContent = AppState.metrics.success;
    DOM.errorOps.textContent = AppState.metrics.error;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
    });
}

function scrollTools() {
    requestAnimationFrame(() => {
        DOM.toolsTimeline.scrollTop = DOM.toolsTimeline.scrollHeight;
    });
}

function generateId() {
    return `exec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// ============================================
// USER INPUT HANDLING
// ============================================

function sendMessage() {
    const text = DOM.userInput.value.trim();
    if (!text) return;
    
    // Add user message
    addMessage('user', text);
    DOM.userInput.value = '';
    
    // Reset textarea height
    DOM.userInput.style.height = 'auto';
    
    // Update state
    updateState('THINKING');
    
    // Send to backend
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    }).catch(err => {
        console.error('Failed to send:', err);
        addMessage('system', 'Error: Failed to send message');
        updateState('IDLE');
    });
}

// Auto-resize textarea as user types
// EXTENSION POINT: Add character counter, formatting toolbar
DOM.userInput.addEventListener('input', (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
});

// Send on Enter (but allow Shift+Enter for new lines)
DOM.userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

DOM.sendBtn.addEventListener('click', sendMessage);

// ============================================
// CLEAR TOOLS HISTORY
// ============================================

DOM.clearBtn.addEventListener('click', () => {
    // EXTENSION POINT: Add confirmation dialog
    if (!confirm('Clear all tool execution history?')) return;
    
    AppState.executions = [];
    AppState.metrics = { total: 0, success: 0, error: 0 };
    
    DOM.toolsTimeline.innerHTML = `
        <div class="empty-state">
            <p>Waiting for activity...</p>
        </div>
    `;
    
    updateMetrics();
});

// ============================================
// INITIALIZATION
// ============================================

function init() {
    console.log('ValH Interface v2.0 - Minimalistic');
    
    // Connect WebSocket
    const ws = new WebSocketConnection();
    ws.connect();
    
    // Initialize mascot behaviors
    const mascot = new MascotBehaviors();
    
    // EXTENSION POINT: Initialize other features
    // - Keyboard shortcuts
    // - Theme switcher
    // - Settings panel
    // - Voice input
    
    console.log('✓ Initialized');
}

// Start application
init();
document.addEventListener('DOMContentLoaded', () => {
    // 1. Select DOM Elements
    const chatLog = document.getElementById('chat-log');
    const messageForm = document.getElementById('message-form');
    const userInput = document.getElementById('user-input');
    const face = document.querySelector('.face');
    const pupils = document.querySelectorAll('.pupil');
    const eyes = document.querySelectorAll('.eye');

    // 2. Handle Form Submission
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const messageText = userInput.value.trim();
        if (messageText) {
            addMessage('user', messageText);
            userInput.value = ''; // 9. Clear Input
            getAssistantResponse(messageText);
        }
    });
    
    // Allow 'Enter' to submit and 'Shift+Enter' for a new line
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            messageForm.dispatchEvent(new Event('submit'));
        }
    });


    // 3. Display Messages
    function addMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);

        // 4. Markdown & Syntax Highlighting
        messageDiv.innerHTML = marked.parse(message);
        
        chatLog.appendChild(messageDiv);
        
        // Apply syntax highlighting after the message is in the DOM
        hljs.highlightAll();

        // 8. Auto-Scrolling
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // 5. Mock Assistant Response
    function getAssistantResponse(userMessage) {
        // 6. "Thinking" Indicator
        face.classList.add('thinking');

        setTimeout(() => {
            const response = `You said: "${userMessage}"\n\n\`\`\`javascript\nconsole.log("This is a highlighted code block!");\n\`\`\``;
            addMessage('assistant', response);
            face.classList.remove('thinking');
        }, 1500); // Simulate a 1.5-second delay
    }

    // 7. Preserve Face Animations
    // Randomly move pupils
    const movePupils = () => {
        pupils.forEach(pupil => {
            const randomX = Math.floor(Math.random() * 3);
            let transform;
            switch (randomX) {
                case 0: transform = 'translate(-100%, -50%)'; break; // Left
                case 1: transform = 'translate(0%, -50%)'; break;    // Right
                default: transform = 'translate(-50%, -50%)'; break; // Center
            }
            pupil.style.transform = transform;
        });
    };

    // Random blinking
    function blink() {
        eyes.forEach(eye => {
            eye.classList.add('blink');
            setTimeout(() => {
                eye.classList.remove('blink');
            }, 400);
        });
    }

    setInterval(movePupils, 2000); // Move every 2 seconds
    setInterval(blink, () => Math.random() * 5000 + 2000); // Blink every 2-7 seconds
});

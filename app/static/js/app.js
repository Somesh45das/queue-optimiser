/**
 * Smart Hospital Queue – Frontend JavaScript
 */

// Live clock
function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const el = document.getElementById('live-clock');
    if (el) el.textContent = timeStr;
}

setInterval(updateClock, 1000);
updateClock();

// Auto-refresh queue page every 30 seconds
if (window.location.pathname.includes('/queue')) {
    setTimeout(() => {
        window.location.reload();
    }, 30000);
}

// Requirement 13.6: admin dashboard refreshes statistics every 60 seconds.
if (/^\/admin\/?$/.test(window.location.pathname)) {
    setTimeout(() => {
        window.location.reload();
    }, 60000);
}

// Tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
    
    // Initialize chatbot
    initChatbot();
});

// ===== Chatbot Functionality =====
function initChatbot() {
    const chatbotButton = document.getElementById('chatbot-button');
    const chatbotWindow = document.getElementById('chatbot-window');
    const chatbotClose = document.getElementById('chatbot-close');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotSend = document.getElementById('chatbot-send');
    const chatbotMessages = document.getElementById('chatbot-messages');
    
    if (!chatbotButton) return;
    
    // Toggle chatbot window
    chatbotButton.addEventListener('click', () => {
        chatbotWindow.classList.toggle('active');
        if (chatbotWindow.classList.contains('active')) {
            chatbotInput.focus();
            // Send greeting if first time
            if (chatbotMessages.children.length === 0) {
                sendMessage('Hello');
            }
        }
    });
    
    chatbotClose.addEventListener('click', () => {
        chatbotWindow.classList.remove('active');
    });
    
    // Send message on button click
    chatbotSend.addEventListener('click', () => {
        const message = chatbotInput.value.trim();
        if (message) {
            sendMessage(message);
            chatbotInput.value = '';
        }
    });
    
    // Send message on Enter key
    chatbotInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const message = chatbotInput.value.trim();
            if (message) {
                sendMessage(message);
                chatbotInput.value = '';
            }
        }
    });
}

function sendMessage(message) {
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotSend = document.getElementById('chatbot-send');
    
    // Add user message
    addChatMessage(message, 'user');
    
    // Show typing indicator
    showTypingIndicator();
    
    // Disable send button
    chatbotSend.disabled = true;
    
    // Send to backend
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const headers = { 'Content-Type': 'application/json' };
    if (csrfMeta) {
        // Requirement 22.5: CSRFProtect validates this header for AJAX posts.
        headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
    }

    fetch('/chatbot/message', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
            message: message,
            context: {}
        })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        hideTypingIndicator();
        
        // Add bot response
        addChatMessage(data.response, 'bot', data.suggestions);
        
        // Enable send button
        chatbotSend.disabled = false;
    })
    .catch(error => {
        console.error('Chatbot error:', error);
        hideTypingIndicator();
        addChatMessage('Sorry, I encountered an error. Please try again.', 'bot');
        chatbotSend.disabled = false;
    });
}

function addChatMessage(text, sender, suggestions = []) {
    const chatbotMessages = document.getElementById('chatbot-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';
    bubbleDiv.textContent = text;
    
    messageDiv.appendChild(bubbleDiv);
    
    // Add suggestions if provided
    if (suggestions && suggestions.length > 0) {
        const suggestionsDiv = document.createElement('div');
        suggestionsDiv.className = 'chat-suggestions';
        
        suggestions.forEach(suggestion => {
            const btn = document.createElement('button');
            btn.className = 'suggestion-btn';
            btn.textContent = suggestion;
            btn.onclick = () => {
                sendMessage(suggestion);
            };
            suggestionsDiv.appendChild(btn);
        });
        
        messageDiv.appendChild(suggestionsDiv);
    }
    
    chatbotMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function showTypingIndicator() {
    const chatbotMessages = document.getElementById('chatbot-messages');
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message bot';
    typingDiv.id = 'typing-indicator';
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble typing-indicator';
    bubbleDiv.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    
    typingDiv.appendChild(bubbleDiv);
    chatbotMessages.appendChild(typingDiv);
    
    // Scroll to bottom
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}


// ===== Responsive navigation and dashboard micro-interactions =====
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const menuToggle = document.querySelector('[data-sidebar-toggle]');

    if (sidebar && menuToggle) {
        const closeSidebar = () => {
            sidebar.classList.remove('mobile-open');
            menuToggle.setAttribute('aria-label', 'Open navigation');
            menuToggle.setAttribute('aria-expanded', 'false');
        };

        menuToggle.addEventListener('click', () => {
            const isOpen = sidebar.classList.toggle('mobile-open');
            menuToggle.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');
            menuToggle.setAttribute('aria-expanded', String(isOpen));
        });

        sidebar.querySelectorAll('.nav-link').forEach((link) => {
            link.addEventListener('click', closeSidebar);
        });

        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) closeSidebar();
        });
    }

    document.querySelectorAll('.stat-card h3, .stat-value').forEach((element) => {
        const value = element.textContent.trim();
        if (!/^\d+$/.test(value) || element.dataset.counted) return;

        const target = Number(value);
        const duration = 550;
        const startedAt = performance.now();
        element.dataset.counted = 'true';

        const updateValue = (now) => {
            const progress = Math.min((now - startedAt) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            element.textContent = Math.round(target * eased);
            if (progress < 1) requestAnimationFrame(updateValue);
        };

        requestAnimationFrame(updateValue);
    });
});


// ===== Brand splash + 3D interaction layer =========================
(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // One-time medical-crest splash. Skip after the first visit per tab so
    // navigating between pages doesn't replay it every click.
    const splash = document.getElementById('brand-splash');
    if (splash) {
        const alreadyShown = sessionStorage.getItem('splashShown') === '1';
        if (reduceMotion || alreadyShown) {
            splash.remove();
        } else {
            sessionStorage.setItem('splashShown', '1');
            const dismiss = () => splash.remove();
            splash.addEventListener('animationend', (event) => {
                if (event.animationName === 'splash-out') dismiss();
            });
            // Hard fallback: remove after 4s in case the animation is skipped
            // by the browser (e.g. background tab throttling).
            setTimeout(dismiss, 4000);
        }
    }

    if (reduceMotion) return;

    // Mouse-follow tilt for hero-ish surfaces. Only applied to elements
    // large enough for the effect to feel deliberate.
    const tiltTargets = document.querySelectorAll(
        '.stat-card, .action-card, .department-card, .appointment-card, .section-card'
    );

    const maxRotate = 6;   // degrees
    const lift = 8;        // px
    let rafId = null;
    let pendingUpdate = null;

    const applyTilt = (element, rx, ry, z) => {
        element.style.transform =
            `translateZ(${z}px) rotateX(${rx}deg) rotateY(${ry}deg)`;
    };

    tiltTargets.forEach((element) => {
        element.addEventListener('pointermove', (event) => {
            if (event.pointerType === 'touch') return;
            const rect = element.getBoundingClientRect();
            const dx = (event.clientX - rect.left) / rect.width - 0.5;
            const dy = (event.clientY - rect.top) / rect.height - 0.5;
            pendingUpdate = () => applyTilt(
                element,
                (-dy * maxRotate).toFixed(2),
                (dx * maxRotate).toFixed(2),
                lift
            );
            if (rafId === null) {
                rafId = requestAnimationFrame(() => {
                    if (pendingUpdate) pendingUpdate();
                    rafId = null;
                });
            }
        });

        element.addEventListener('pointerleave', () => {
            element.style.transform = '';
        });
    });
})();

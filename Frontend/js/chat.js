/**
 * chat.js — Handles chat UI, message sending, and fake AI responses
 * DocuMind AI Frontend
 *
 * Architecture note:
 *   - All messages are tracked in `conversationHistory[]`
 *   - Fake AI responses simulate a RAG-style document assistant
 *   - Replace `getFakeAIResponse()` with an actual fetch() call to your FastAPI backend
 */

/* ── Page loader ──────────────────────────────────────── */
window.addEventListener('load', () => {
  const loader = document.getElementById('pageLoader');
  if (loader) setTimeout(() => loader.classList.add('hidden'), 300);
});

/* ── DOM references ───────────────────────────────────── */
const chatMessages   = document.getElementById('chatMessages');
const chatInput      = document.getElementById('chatInput');
const sendBtn        = document.getElementById('sendBtn');
const newChatBtn     = document.getElementById('newChatBtn');
const clearChatBtn   = document.getElementById('clearChatBtn');
const welcomeBanner  = document.getElementById('welcomeBanner');
const demoMsg1       = document.getElementById('demoMsg1');
const demoMsg2       = document.getElementById('demoMsg2');

/* ── State ────────────────────────────────────────────── */
let isWaiting         = false;      // Prevent double-send
let conversationHistory = [];       // For future backend integration

/* ── Fake AI response bank ────────────────────────────── */
const AI_RESPONSES = {
  'semester fee': `You can pay your semester fee through the <strong>university portal</strong> at <em>portal.university.edu</em>.<br><br>Steps:<br>1. Log in with your student credentials<br>2. Navigate to <strong>Finances → Semester Fee</strong><br>3. Choose your payment method<br>4. Download your receipt<br><br>⚠️ The current semester deadline is <strong>March 31, 2026</strong>.`,
  'hostel': `To apply for hostel accommodation:<br><br>1. Visit the <strong>Student Services portal</strong><br>2. Select <strong>Accommodation → Apply for Hostel</strong><br>3. Fill in the application form and upload required documents<br>4. Pay the hostel deposit (PKR 15,000)<br><br>Applications for the next academic year open on <strong>April 1, 2026</strong>. Priority is given to first-year students.`,
  'attendance': `The university's attendance policy requires a minimum of <strong>75% attendance</strong> in each course.<br><br>Key points:<br>• Below 75% → barred from final exams<br>• Medical absences must be reported within 48 hours<br>• Attendance is recorded per lecture, not per day<br><br>You can check your current attendance on the <strong>LMS portal</strong>.`,
  'exam': `Exam schedules are typically released <strong>3 weeks</strong> before the examination period.<br><br>For the Spring 2026 semester:<br>• Mid-term exams: April 14–20, 2026<br>• Final exams: June 10–24, 2026<br><br>Check the <strong>Academics section</strong> of the portal for your personal timetable.`,
  'library': `The university library is open:<br><br>• Monday–Friday: <strong>8:00 AM – 10:00 PM</strong><br>• Saturday: <strong>9:00 AM – 6:00 PM</strong><br>• Sunday: <strong>Closed</strong><br><br>Students can borrow up to <strong>5 books</strong> for 14 days. Renewals are allowed twice online.`,
  'default': `I found relevant information in your uploaded documents. Based on the available knowledge base, this query falls under institutional policy. Please check the <strong>Student Handbook 2026</strong> for detailed guidelines, or contact the relevant department directly.<br><br>Is there anything more specific I can help you with?`
};

/* ── Helpers ──────────────────────────────────────────── */

/** Format current time as HH:MM AM/PM */
function getTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** Get keyword-matched fake AI response */
function getFakeAIResponse(userMsg) {
  const lower = userMsg.toLowerCase();
  for (const [key, response] of Object.entries(AI_RESPONSES)) {
    if (key !== 'default' && lower.includes(key)) return response;
  }
  return AI_RESPONSES.default;
}

/** Create a message row element */
function createMsgRow(text, role, time) {
  const isUser = role === 'user';
  const row = document.createElement('div');
  row.className = `msg-row ${isUser ? 'user' : 'ai'}`;

  const avatar = document.createElement('div');
  avatar.className = `msg-avatar ${isUser ? 'user-avatar' : 'ai-avatar'}`;
  avatar.textContent = isUser ? 'JD' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = text;

  const timeEl = document.createElement('div');
  timeEl.className = 'msg-time';
  timeEl.textContent = time;

  const wrapper = document.createElement('div');
  wrapper.appendChild(bubble);
  wrapper.appendChild(timeEl);

  if (isUser) {
    row.appendChild(wrapper);
    row.appendChild(avatar);
  } else {
    row.appendChild(avatar);
    row.appendChild(wrapper);
  }

  return row;
}

/** Create typing indicator row */
function createTypingIndicator() {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  row.id = 'typingIndicator';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar ai-avatar';
  avatar.textContent = 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.style.padding = '14px 18px';
  bubble.innerHTML = `<div class="typing-indicator">
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  </div>`;

  row.appendChild(avatar);
  row.appendChild(bubble);
  return row;
}

/** Scroll to bottom of chat window */
function scrollToBottom() {
  chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
}

/** Show/hide welcome banner */
function hideBanner() {
  if (welcomeBanner) welcomeBanner.style.display = 'none';
  // Show the seeded demo conversation
  if (demoMsg1) demoMsg1.style.display = 'flex';
  if (demoMsg2) demoMsg2.style.display = 'flex';
}

/* ── Send message flow ────────────────────────────────── */
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || isWaiting) return;

  isWaiting = true;
  sendBtn.disabled = true;
  hideBanner();

  // Track message in history
  conversationHistory.push({ role: 'user', content: text });

  // Render user message
  const userRow = createMsgRow(text, 'user', getTime());
  chatMessages.appendChild(userRow);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  scrollToBottom();

  // Show typing indicator with slight delay
  await new Promise(r => setTimeout(r, 300));
  const typingRow = createTypingIndicator();
  chatMessages.appendChild(typingRow);
  scrollToBottom();

  // Simulate AI processing time (800ms – 1600ms)
  const delay = 800 + Math.random() * 800;
  await new Promise(r => setTimeout(r, delay));

  // Remove typing indicator
  typingRow.remove();

  // Get and render AI response
  const aiText = getFakeAIResponse(text);
  conversationHistory.push({ role: 'assistant', content: aiText });

  const aiRow = createMsgRow(aiText, 'ai', getTime() + ' · Sourced from knowledge base');
  chatMessages.appendChild(aiRow);
  scrollToBottom();

  isWaiting = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

/* ── Event: Send button click ─────────────────────────── */
sendBtn.addEventListener('click', sendMessage);

/* ── Event: Enter key to send (Shift+Enter = newline) ─── */
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

/* ── Event: Enable/disable send button dynamically ────── */
chatInput.addEventListener('input', () => {
  sendBtn.disabled = chatInput.value.trim() === '' || isWaiting;
  // Auto-resize textarea
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

/* ── Event: Suggestion chips ──────────────────────────── */
document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    chatInput.value = chip.dataset.msg;
    sendBtn.disabled = false;
    sendMessage();
  });
});

/* ── Event: New chat button ───────────────────────────── */
newChatBtn.addEventListener('click', () => {
  // Clear messages and restore welcome banner
  chatMessages.innerHTML = '';
  conversationHistory = [];

  // Re-create welcome banner
  const banner = document.createElement('div');
  banner.id = 'welcomeBanner';
  banner.style.cssText = 'text-align:center;padding:32px 16px;';
  banner.innerHTML = `
    <div style="width:52px;height:52px;background:var(--primary-light);border-radius:var(--radius-md);display:flex;align-items:center;justify-content:center;margin:0 auto 12px;color:var(--primary);">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </div>
    <h5 style="font-size:1rem;margin-bottom:6px;">New conversation started</h5>
    <p style="color:var(--text-muted);font-size:.82rem;max-width:340px;margin:0 auto;">Ask me anything about your organization's documents.</p>
  `;
  chatMessages.appendChild(banner);
  chatInput.focus();
  isWaiting = false;
  sendBtn.disabled = true;
});

/* ── Event: Clear chat ────────────────────────────────── */
clearChatBtn.addEventListener('click', () => {
  newChatBtn.click();
});

/* ── Sidebar item click (cosmetic) ────────────────────── */
document.querySelectorAll('.sidebar-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
  });
});

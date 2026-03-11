/**
 * login.js — Handles login form validation and redirect
 * DocuMind AI Frontend
 */

/* ── Page loader ──────────────────────────────────────── */
window.addEventListener('load', () => {
  const loader = document.getElementById('pageLoader');
  if (loader) {
    setTimeout(() => loader.classList.add('hidden'), 300);
  }
});

/* ── DOM references ───────────────────────────────────── */
const loginForm  = document.getElementById('loginForm');
const orgInput   = document.getElementById('orgName');
const emailInput = document.getElementById('email');
const pwdInput   = document.getElementById('password');
const loginBtn   = document.getElementById('loginBtn');
const togglePwd  = document.getElementById('togglePwd');
const eyeIcon    = document.getElementById('eyeIcon');

/* ── Password visibility toggle ───────────────────────── */
togglePwd.addEventListener('click', () => {
  const isPassword = pwdInput.type === 'password';
  pwdInput.type = isPassword ? 'text' : 'password';

  // Swap icon between eye and eye-off
  eyeIcon.innerHTML = isPassword
    ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
       <line x1="1" y1="1" x2="23" y2="23"/>`
    : `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
       <circle cx="12" cy="12" r="3"/>`;
});

/* ── Simple field validators ───────────────────────────── */
function validateEmail(val) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
}

function showError(fieldId, show) {
  const el = document.getElementById(fieldId);
  if (el) el.style.display = show ? 'block' : 'none';
}

function markInput(input, valid) {
  input.style.borderColor = valid ? '' : '#ef4444';
  if (valid) input.style.borderColor = '';
}

/* ── Real-time validation (clear errors on input) ──────── */
orgInput.addEventListener('input', () => {
  showError('orgError', false);
  markInput(orgInput, true);
});

emailInput.addEventListener('input', () => {
  showError('emailError', false);
  markInput(emailInput, true);
});

pwdInput.addEventListener('input', () => {
  showError('pwdError', false);
  markInput(pwdInput, true);
});

/* ── Form submit handler ───────────────────────────────── */
loginForm.addEventListener('submit', (e) => {
  e.preventDefault();

  const org   = orgInput.value.trim();
  const email = emailInput.value.trim();
  const pwd   = pwdInput.value;

  let valid = true;

  // Validate organization
  if (!org) {
    showError('orgError', true);
    markInput(orgInput, false);
    valid = false;
  }

  // Validate email
  if (!validateEmail(email)) {
    showError('emailError', true);
    markInput(emailInput, false);
    valid = false;
  }

  // Validate password length
  if (pwd.length < 6) {
    showError('pwdError', true);
    markInput(pwdInput, false);
    valid = false;
  }

  if (!valid) return;

  // ── Simulate login loading state ──────────────────────
  loginBtn.disabled = true;
  loginBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"
      style="animation:spin .8s linear infinite;">
      <line x1="12" y1="2" x2="12" y2="6"/>
      <line x1="12" y1="18" x2="12" y2="22"/>
      <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>
      <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
      <line x1="2" y1="12" x2="6" y2="12"/>
      <line x1="18" y1="12" x2="22" y2="12"/>
      <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>
      <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>
    </svg>
    Signing in…
  `;

  // Add spin keyframe if not present
  if (!document.getElementById('spinStyle')) {
    const style = document.createElement('style');
    style.id = 'spinStyle';
    style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
    document.head.appendChild(style);
  }

  // Store user session info (dummy)
  sessionStorage.setItem('dm_user', JSON.stringify({ org, email, name: email.split('@')[0] }));

  // Redirect to chat after brief delay
  setTimeout(() => {
    window.location.href = 'chat.html';
  }, 900);
});

/* ── Auto-fill hint for demo purposes ────────────────────
   Pre-fill fields if visiting from a demo link
────────────────────────────────────────────────────────── */
const params = new URLSearchParams(window.location.search);
if (params.get('demo') === '1') {
  orgInput.value   = 'Acme University';
  emailInput.value = 'admin@acme.edu';
  pwdInput.value   = 'demo123';
}

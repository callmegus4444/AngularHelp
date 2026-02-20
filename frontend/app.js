/**
 * app.js — AngularHelp Frontend
 * ================================
 * Client-side logic for the three-panel UI:
 *   1. Session management (UUID persisted in sessionStorage)
 *   2. Main generation flow (hero → result panel with tabs)
 *   3. Chat panel memory (build history + follow-up prompts)
 *   4. Code viewer with sub-tabs & copy
 *   5. Preview iframe integration
 */

'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────

const state = {
    sessionId: null,
    lastComponent: null,   // { ts, html, scss, name }
    activeCodeTab: 'ts',
    activeMainTab: 'code',
};

// ─────────────────────────────────────────────────────────────────────────────
// DOM refs  (initialised once DOM is ready)
// ─────────────────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const DOM = {};

function initDOM() {
    DOM.mainLayout = $('mainLayout');
    DOM.hero = $('hero');
    DOM.resultPanel = $('resultPanel');
    DOM.chatPanel = $('chatPanel');
    DOM.chatMessages = $('chatMessages');

    DOM.mainPrompt = $('mainPrompt');
    DOM.btnGenerate = $('btnGenerate');
    DOM.followupPrompt = $('followupPrompt');
    DOM.btnFollowup = $('btnFollowup');
    DOM.chatPrompt = $('chatPrompt');
    DOM.btnChatSend = $('btnChatSend');
    DOM.btnNewSession = $('btnNewSession');
    DOM.btnClearChat = $('btnClearChat');
    DOM.btnCopy = $('btnCopy');
    DOM.btnOpenPreview = $('btnOpenPreview');

    DOM.sessionBadge = $('sessionBadge');
    DOM.componentName = $('componentNameLabel');
    DOM.validationBadge = $('validationBadge');
    DOM.codeBlock = $('codeBlock');
    DOM.previewFrame = $('previewFrame');
    DOM.previewUrl = $('previewUrl');
    DOM.loadingOverlay = $('loadingOverlay');
    DOM.loadingText = $('loadingText');
    DOM.toast = $('toast');

    DOM.tabCode = $('tabCode');
    DOM.tabPreview = $('tabPreview');
    DOM.tabContentCode = $('tabContentCode');
    DOM.tabContentPreview = $('tabContentPreview');
}

// ─────────────────────────────────────────────────────────────────────────────
// Session bootstrap
// ─────────────────────────────────────────────────────────────────────────────

async function bootstrapSession() {
    let sid = sessionStorage.getItem('cb_session_id');

    if (!sid) {
        try {
            const res = await fetch('/api/new-session');
            const data = await res.json();
            sid = data.session_id;
            sessionStorage.setItem('cb_session_id', sid);
        } catch {
            // Server might not be running yet — generate a client-side UUID as fallback
            sid = crypto.randomUUID();
            sessionStorage.setItem('cb_session_id', sid);
        }
    }

    state.sessionId = sid;
    DOM.sessionBadge.textContent = `Session ${sid.slice(0, 8)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────

async function callGenerate(prompt) {
    const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId, prompt }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Generation flow
// ─────────────────────────────────────────────────────────────────────────────

async function generate(prompt) {
    if (!prompt.trim()) { showToast('Please enter a description first.'); return; }

    setLoading(true, 'Thinking…');

    try {
        const data = await callGenerate(prompt);

        // Update session id in case the server assigned one
        if (data.session_id) {
            state.sessionId = data.session_id;
            sessionStorage.setItem('cb_session_id', data.session_id);
            DOM.sessionBadge.textContent = `Session ${data.session_id.slice(0, 8)}`;
        }

        // Cache component locally
        state.lastComponent = {
            name: data.component_name,
            ts: data.typescript_code,
            html: data.html_template,
            scss: data.scss_styles,
        };

        renderResult(data);
        renderChatLog(data.chat_log);
        showResultPanel();
        showChatPanel();

    } catch (err) {
        showToast(`❌ ${err.message}`, 4000);
        console.error(err);
    } finally {
        setLoading(false);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Render result panel
// ─────────────────────────────────────────────────────────────────────────────

function renderResult(data) {
    DOM.componentName.textContent = data.component_name;
    DOM.validationBadge.textContent = data.validation_passed ? '✅ passed' : '⚠️ warnings';

    // Default to Code tab
    switchMainTab('code');
    switchCodeSubTab('ts');

    // Pre-cache code strings so switching tabs doesn't re-fetch
    state.lastComponent = {
        name: data.component_name,
        ts: data.typescript_code,
        html: data.html_template,
        scss: data.scss_styles,
    };

    showCode('ts');
}

function showCode(lang) {
    const map = { ts: state.lastComponent?.ts, html: state.lastComponent?.html, scss: state.lastComponent?.scss };
    const langMap = { ts: 'typescript', html: 'xml', scss: 'css' };

    DOM.codeBlock.className = `language-${langMap[lang]}`;
    DOM.codeBlock.textContent = map[lang] || '';
    hljs.highlightElement(DOM.codeBlock);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab switching
// ─────────────────────────────────────────────────────────────────────────────

function switchMainTab(tab) {
    state.activeMainTab = tab;

    DOM.tabCode.classList.toggle('active', tab === 'code');
    DOM.tabPreview.classList.toggle('active', tab === 'preview');
    DOM.tabContentCode.classList.toggle('hidden', tab !== 'code');
    DOM.tabContentPreview.classList.toggle('hidden', tab !== 'preview');

    if (tab === 'preview') {
        loadPreview();
    }
}

function loadPreview() {
    const url = `/api/preview/${state.sessionId}`;
    DOM.previewFrame.src = url;
    DOM.previewUrl.textContent = url;
}

function switchCodeSubTab(lang) {
    state.activeCodeTab = lang;
    document.querySelectorAll('.code-sub-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.codetab === lang);
    });
    showCode(lang);
}

// ─────────────────────────────────────────────────────────────────────────────
// Show/hide panels
// ─────────────────────────────────────────────────────────────────────────────

function showResultPanel() {
    DOM.hero.classList.add('hidden');
    DOM.resultPanel.classList.remove('hidden');
}

function showHero() {
    DOM.resultPanel.classList.add('hidden');
    DOM.hero.classList.remove('hidden');
}

function showChatPanel() {
    DOM.chatPanel.classList.remove('hidden');
    DOM.mainLayout.classList.add('with-chat');
}

function hideChatPanel() {
    DOM.chatPanel.classList.add('hidden');
    DOM.mainLayout.classList.remove('with-chat');
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat panel rendering
// ─────────────────────────────────────────────────────────────────────────────

function renderChatLog(log) {
    if (!log || log.length === 0) return;
    DOM.chatMessages.innerHTML = '';

    log.forEach(entry => {
        appendChatEntry(entry.role, entry.content, entry.summary || '');
    });

    // Scroll to bottom
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
}

function appendChatEntry(role, content, summary = '') {
    const wrap = document.createElement('div');
    wrap.className = 'chat-entry';

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble--${role}`;
    bubble.textContent = content;
    wrap.appendChild(bubble);

    if (role === 'assistant' && summary) {
        const pill = document.createElement('div');
        pill.className = 'chat-summary-pill';
        pill.innerHTML = `
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      ${summary}`;
        wrap.appendChild(pill);
    }

    const ts = document.createElement('div');
    ts.className = 'chat-timestamp';
    ts.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    wrap.appendChild(ts);

    DOM.chatMessages.appendChild(wrap);
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
}

// ─────────────────────────────────────────────────────────────────────────────
// Session management
// ─────────────────────────────────────────────────────────────────────────────

async function resetSession() {
    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.sessionId }),
        });
        const data = await res.json();
        state.sessionId = data.session_id;
        sessionStorage.setItem('cb_session_id', data.session_id);
        DOM.sessionBadge.textContent = `Session ${data.session_id.slice(0, 8)}`;
    } catch {
        const sid = crypto.randomUUID();
        state.sessionId = sid;
        sessionStorage.setItem('cb_session_id', sid);
        DOM.sessionBadge.textContent = `Session ${sid.slice(0, 8)}`;
    }

    state.lastComponent = null;
    DOM.chatMessages.innerHTML = '';
    DOM.mainPrompt.value = '';
    hideChatPanel();
    showHero();
    showToast('🔄 New session started');
}

// ─────────────────────────────────────────────────────────────────────────────
// Copy to clipboard
// ─────────────────────────────────────────────────────────────────────────────

async function copyCode() {
    const map = { ts: state.lastComponent?.ts, html: state.lastComponent?.html, scss: state.lastComponent?.scss };
    const text = map[state.activeCodeTab] || '';
    try {
        await navigator.clipboard.writeText(text);
        showToast('✅ Copied to clipboard');
    } catch {
        showToast('❌ Copy failed — try selecting manually');
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Loading overlay
// ─────────────────────────────────────────────────────────────────────────────

const loadingMessages = [
    'Thinking…',
    'Designing your component…',
    'Applying design system…',
    'Validating output…',
    'Almost there…',
];

let loadingInterval = null;

function setLoading(active, initialText = 'Thinking…') {
    DOM.loadingOverlay.classList.toggle('hidden', !active);
    DOM.btnGenerate.disabled = active;
    DOM.btnFollowup.disabled = active;
    DOM.btnChatSend.disabled = active;

    if (active) {
        DOM.loadingText.textContent = initialText;
        let idx = 0;
        loadingInterval = setInterval(() => {
            idx = (idx + 1) % loadingMessages.length;
            DOM.loadingText.textContent = loadingMessages[idx];
        }, 2000);
    } else {
        clearInterval(loadingInterval);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast notifications
// ─────────────────────────────────────────────────────────────────────────────

let toastTimer = null;

function showToast(msg, duration = 3000) {
    DOM.toast.textContent = msg;
    DOM.toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => DOM.toast.classList.add('hidden'), duration);
}

// ─────────────────────────────────────────────────────────────────────────────
// Auto-resize textareas
// ─────────────────────────────────────────────────────────────────────────────

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Event listeners
// ─────────────────────────────────────────────────────────────────────────────

function bindEvents() {
    // ── Main prompt ────────────────────────────────────────────────────
    DOM.mainPrompt.addEventListener('input', () => autoResize(DOM.mainPrompt));
    DOM.mainPrompt.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            generate(DOM.mainPrompt.value.trim());
        }
    });
    DOM.btnGenerate.addEventListener('click', () => generate(DOM.mainPrompt.value.trim()));

    // ── Hint pills ─────────────────────────────────────────────────────
    document.querySelectorAll('.hint-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const p = pill.dataset.prompt;
            DOM.mainPrompt.value = p;
            autoResize(DOM.mainPrompt);
            generate(p);
        });
    });

    // ── Main tabs ──────────────────────────────────────────────────────
    DOM.tabCode.addEventListener('click', () => switchMainTab('code'));
    DOM.tabPreview.addEventListener('click', () => switchMainTab('preview'));

    // ── Code sub-tabs ──────────────────────────────────────────────────
    document.querySelectorAll('.code-sub-tab').forEach(btn => {
        btn.addEventListener('click', () => switchCodeSubTab(btn.dataset.codetab));
    });

    // ── Copy button ────────────────────────────────────────────────────
    DOM.btnCopy.addEventListener('click', copyCode);

    // ── Open preview in new tab ────────────────────────────────────────
    DOM.btnOpenPreview.addEventListener('click', () => {
        window.open(`/api/preview/${state.sessionId}`, '_blank');
    });

    // ── Follow-up prompt (under result) ───────────────────────────────
    DOM.followupPrompt.addEventListener('input', () => autoResize(DOM.followupPrompt));
    DOM.followupPrompt.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const p = DOM.followupPrompt.value.trim();
            DOM.followupPrompt.value = '';
            autoResize(DOM.followupPrompt);
            generate(p);
        }
    });
    DOM.btnFollowup.addEventListener('click', () => {
        const p = DOM.followupPrompt.value.trim();
        DOM.followupPrompt.value = '';
        autoResize(DOM.followupPrompt);
        generate(p);
    });

    // ── Chat panel send ────────────────────────────────────────────────
    DOM.chatPrompt.addEventListener('input', () => autoResize(DOM.chatPrompt));
    DOM.chatPrompt.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChat();
        }
    });
    DOM.btnChatSend.addEventListener('click', sendChat);

    // ── New session ────────────────────────────────────────────────────
    DOM.btnNewSession.addEventListener('click', resetSession);

    // ── Clear chat (just the panel, not the server session) ───────────
    DOM.btnClearChat.addEventListener('click', () => {
        DOM.chatMessages.innerHTML = '';
        showToast('Chat cleared');
    });
}

async function sendChat() {
    const p = DOM.chatPrompt.value.trim();
    if (!p) return;
    DOM.chatPrompt.value = '';
    autoResize(DOM.chatPrompt);
    await generate(p);
}

// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    initDOM();
    bindEvents();
    await bootstrapSession();
});

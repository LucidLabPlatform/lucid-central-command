// AI assistant page — workflow planning and execution
let convId = null;

const messagesEl = document.getElementById('ai-messages');
const inputEl    = document.getElementById('ai-input');
const sendBtn    = document.getElementById('ai-send');

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

function esc(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendUserMsg(text) {
  const div = document.createElement('div');
  div.className = 'ai-msg ai-msg-user';
  div.innerHTML = `<span class="ai-msg-label">You</span><div class="ai-msg-body">${esc(text)}</div>`;
  messagesEl.appendChild(div);
  scrollBottom();
}

function appendAiMsg(id) {
  const div = document.createElement('div');
  div.className = 'ai-msg ai-msg-assistant';
  div.innerHTML = `
    <span class="ai-msg-label">LUCID AI</span>
    <div class="ai-msg-body" id="${id}">
      <span class="ai-thinking">
        <span class="ai-spinner"></span>thinking…
      </span>
    </div>`;
  messagesEl.appendChild(div);
  scrollBottom();
  return document.getElementById(id);
}

function setMsgContent(bodyEl, html) {
  bodyEl.innerHTML = html;
  scrollBottom();
}

// ---------------------------------------------------------------------------
// Plan card
// ---------------------------------------------------------------------------

function renderPlanCard(plan, bodyEl) {
  const stepsHtml = plan.steps.map(s => `
    <li class="ai-plan-step" id="ps-${s.step_number}">
      <span class="ai-plan-step-icon">○</span>
      <span class="ai-plan-step-title">${esc(s.title)}</span>
      <span class="ai-plan-step-type">${esc(s.action_type)}</span>
    </li>`).join('');

  const card = document.createElement('div');
  card.className = 'ai-plan-card';
  card.innerHTML = `
    <div class="ai-plan-title">${esc(plan.title)}</div>
    <div class="ai-plan-desc">${esc(plan.description || '')}</div>
    <ol class="ai-plan-steps">${stepsHtml}</ol>
    <div class="ai-plan-actions">
      <button class="btn-primary" id="btn-approve">Approve &amp; Run</button>
      <button class="btn-sm" id="btn-reject">Reject</button>
    </div>`;
  bodyEl.appendChild(card);
  scrollBottom();

  document.getElementById('btn-approve').addEventListener('click', () => approvePlan(plan, card));
  document.getElementById('btn-reject').addEventListener('click', () => rejectPlan(card));
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

async function approvePlan(plan, card) {
  card.querySelector('#btn-approve').disabled = true;
  card.querySelector('#btn-reject').disabled  = true;

  await fetch(`${AI_URL}/conversations/${convId}/approve`, { method: 'POST' });

  // Add execution log block
  const execBodyEl = appendAiMsg('ai-exec-body');
  const logDiv = document.createElement('div');
  logDiv.className = 'ai-exec-log';
  logDiv.id = 'exec-log';
  execBodyEl.innerHTML = '';
  execBodyEl.appendChild(logDiv);

  const es = new EventSource(`${AI_URL}/conversations/${convId}/execute`);
  es.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }
    handleExecEvent(data, plan);
    if (data.type === 'done' || data.type === 'error') {
      es.close();
      // Allow a new message after execution
      convId = null;
      sendBtn.disabled = false;
    }
  };
  es.onerror = () => {
    es.close();
    appendExecLine('Connection lost.', false);
    convId = null;
    sendBtn.disabled = false;
  };
}

function handleExecEvent(data, plan) {
  const log = document.getElementById('exec-log');
  if (!log) return;

  if (data.type === 'step_start') {
    const item = document.createElement('div');
    item.className = 'ai-exec-step';
    item.id = `es-${data.step}`;
    item.innerHTML = `<span class="ai-spinner"></span>${esc(data.title)}`;
    log.appendChild(item);
    scrollBottom();

  } else if (data.type === 'step_done') {
    const item = document.getElementById(`es-${data.step}`);
    if (item) {
      const icon = data.ok ? '✓' : '✗';
      const cls  = data.ok ? 'ai-exec-ok' : 'ai-exec-err';
      item.innerHTML = `<span class="${cls}">${icon}</span> ${esc(data.title)} <span class="ai-exec-result">${esc(data.result)}</span>`;
    }
    // Mirror result onto plan step icon
    const ps = document.getElementById(`ps-${data.step}`);
    if (ps) {
      const icon = ps.querySelector('.ai-plan-step-icon');
      if (icon) {
        icon.textContent = data.ok ? '✓' : '✗';
        icon.style.color = data.ok ? 'var(--green)' : 'var(--red)';
      }
    }

  } else if (data.type === 'done') {
    const done = document.createElement('div');
    done.className = 'ai-exec-done';
    done.textContent = 'Workflow complete.';
    log.appendChild(done);
    scrollBottom();

  } else if (data.type === 'error') {
    appendExecLine(`Error: ${data.message}`, false);
  }
}

function appendExecLine(text, ok) {
  const log = document.getElementById('exec-log');
  if (!log) return;
  const item = document.createElement('div');
  item.className = 'ai-exec-step';
  item.innerHTML = `<span class="${ok ? 'ai-exec-ok' : 'ai-exec-err'}">${ok ? '✓' : '✗'}</span> ${esc(text)}`;
  log.appendChild(item);
  scrollBottom();
}

async function rejectPlan(card) {
  await fetch(`${AI_URL}/conversations/${convId}/reject`, { method: 'POST' });
  card.querySelector('#btn-approve').disabled = true;
  card.querySelector('#btn-reject').disabled  = true;

  const note = document.createElement('p');
  note.style.cssText = 'margin-top:0.5rem;color:var(--muted);font-size:0.8rem';
  note.textContent = 'Plan rejected.';
  card.appendChild(note);

  convId = null;
  sendBtn.disabled = false;
}

// ---------------------------------------------------------------------------
// Send message → plan
// ---------------------------------------------------------------------------

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message || sendBtn.disabled) return;

  inputEl.value = '';
  sendBtn.disabled = true;
  appendUserMsg(message);

  // Create a fresh conversation for each planning request
  const resp = await fetch(`${AI_URL}/conversations`, { method: 'POST' });
  const data = await resp.json();
  convId = data.conversation_id;

  const bodyEl = appendAiMsg(`ai-plan-msg-${Date.now()}`);

  let planResp;
  try {
    planResp = await fetch(`${AI_URL}/conversations/${convId}/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
  } catch (err) {
    setMsgContent(bodyEl, `<span style="color:var(--red)">Could not reach lucid-ai service. Is it running on port 6000?</span>`);
    sendBtn.disabled = false;
    convId = null;
    return;
  }

  if (!planResp.ok) {
    const errText = await planResp.text().catch(() => planResp.statusText);
    setMsgContent(bodyEl, `<span style="color:var(--red)">Planning failed: ${esc(errText)}</span>`);
    sendBtn.disabled = false;
    convId = null;
    return;
  }

  const result = await planResp.json();
  const { explanation, plan, status } = result;

  // Render explanation text (strip the JSON code block for cleanliness)
  const cleanExplanation = (explanation || '').replace(/```json[\s\S]*?```/g, '').trim();
  bodyEl.innerHTML = cleanExplanation
    ? `<span style="white-space:pre-wrap">${esc(cleanExplanation)}</span>`
    : '';

  if (plan && status === 'awaiting_approval') {
    renderPlanCard(plan, bodyEl);
    // sendBtn stays disabled until user approves/rejects
  } else {
    bodyEl.innerHTML += `<p style="margin-top:0.5rem;color:var(--yellow)">Couldn't extract a structured plan — try rephrasing your request.</p>`;
    convId = null;
    sendBtn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

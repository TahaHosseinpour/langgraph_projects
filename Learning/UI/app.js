/* ── State ──────────────────────────────────────────────────────────────── */
const state = {
  graphId:      '1',
  threadId:     null,
  currentFile:  null,
  ttThreadId:   null,
  ttError:      null,
  hitlData:     null,
  streamNodes:  {},
};

/* ── DOM refs ───────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

const graphSelect      = $('graphSelect');
const featureBadge     = $('featureBadge');
const chatMessages     = $('chatMessages');
const chatScroll       = $('chatScroll');
const genForm          = $('genForm');
const btnGenerate      = $('btnGenerate');
const btnText          = $('btnText');
const btnSpinner       = $('btnSpinner');
const btnRefresh           = $('btnRefresh');
const previewToolbar       = $('previewToolbar');
const presentationSelect   = $('presentationSelect');
const graphControls        = $('graphControls');
const streamProgress   = $('streamProgress');
const previewEmpty     = $('previewEmpty');
const slideFrame       = $('slideFrame');
const hitlOverlay      = $('hitlOverlay');
const hitlClose        = $('hitlClose');
const hitlApprove      = $('hitlApprove');
const hitlCancel       = $('hitlCancel');
const tabDesign        = $('tabDesign');
const tabSlides        = $('tabSlides');

/* ── Graph metadata ─────────────────────────────────────────────────────── */
const GRAPH_META = {
  '1': { label: null },
  '2': { label: 'Conditional Edges', color: '#1E6FEB', bg: '#EFF6FF' },
  '3': { label: 'Human in the Loop', color: '#C2410C', bg: '#FFF7ED' },
  '4': { label: 'Time Travel',       color: '#15803D', bg: '#F0FDF4' },
  '5': { label: 'Long-term Memory',  color: '#7C3AED', bg: '#EDE9FE' },
  '6': { label: 'Streaming',         color: '#BE123C', bg: '#FFF1F2' },
};

/* ── Init ───────────────────────────────────────────────────────────────── */
graphSelect.addEventListener('change', () => {
  state.graphId   = graphSelect.value;
  state.threadId  = null;
  state.ttThreadId = null;
  state.ttError   = null;
  state.hitlData  = null;
  state.currentFile = null;
  updateBadge();
  updateControls();
  clearPreview();
  clearChat();
  addMessage('assistant', `Switched to <strong>Graph ${state.graphId}</strong>. Fill in the form and click Generate.`);
});

function updateBadge() {
  const meta = GRAPH_META[state.graphId];
  if (meta.label) {
    featureBadge.textContent = meta.label;
    featureBadge.style.background = meta.bg;
    featureBadge.style.color = meta.color;
    featureBadge.style.border = `1px solid ${meta.color}44`;
    featureBadge.classList.remove('hidden');
  } else {
    featureBadge.classList.add('hidden');
  }
}

function updateControls() {
  graphControls.innerHTML = '';
  graphControls.classList.add('hidden');
  streamProgress.innerHTML = '';
  streamProgress.classList.add('hidden');
  state.streamNodes = {};

  if (state.graphId === '4') {
    renderTimeTravelControls();
  }
}

/* ── Chat ───────────────────────────────────────────────────────────────── */
function clearChat() {
  chatMessages.innerHTML = '';
}

function addMessage(role, html) {
  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = html;
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatScroll.scrollTop = chatScroll.scrollHeight;
}

/* ── Preview ────────────────────────────────────────────────────────────── */
/* ── Presentations list ─────────────────────────────────────────────────── */
async function loadPresentationsList() {
  try {
    const files = await (await fetch('/api/presentations')).json();
    rebuildSelect(files);
  } catch { /* server not up yet */ }
}

function rebuildSelect(files) {
  presentationSelect.innerHTML = '<option value="">— saved presentations —</option>';
  files.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f;
    opt.textContent = f.replace(/^g\d_/, '').replace(/_\d{8}_\d{6}\.html$/, '').replace(/_/g, ' ');
    presentationSelect.appendChild(opt);
  });
}

presentationSelect.addEventListener('change', () => {
  const f = presentationSelect.value;
  if (f) renderPreview(f);
});

/* ── Preview ────────────────────────────────────────────────────────────── */
function clearPreview() {
  state.currentFile = null;
  slideFrame.classList.add('hidden');
  slideFrame.removeAttribute('srcdoc');
  slideFrame.removeAttribute('src');
  previewEmpty.classList.remove('hidden');
  btnRefresh.classList.add('hidden');
}

function renderPreview(filename) {
  state.currentFile = filename;
  // Point iframe.src at the saved, self-contained HTML file.
  // NOTE: an empty `srcdoc` attribute overrides `src`, so it must be removed
  // (not set to '') or the iframe renders blank and the HTML never shows.
  slideFrame.removeAttribute('srcdoc');
  slideFrame.src = `/presentations/${filename}`;
  previewEmpty.classList.add('hidden');
  slideFrame.classList.remove('hidden');
  btnRefresh.classList.remove('hidden');
  if (presentationSelect.querySelector(`option[value="${filename}"]`)) {
    presentationSelect.value = filename;
  } else {
    loadPresentationsList().then(() => { presentationSelect.value = filename; });
  }
}

btnRefresh.addEventListener('click', () => {
  if (state.currentFile) {
    slideFrame.src = `/presentations/${state.currentFile}`;
  }
});

/* ── Loading state ──────────────────────────────────────────────────────── */
function setLoading(on) {
  btnGenerate.disabled = on;
  btnText.classList.toggle('hidden', on);
  btnSpinner.classList.toggle('hidden', !on);
}

/* ── Form submit ────────────────────────────────────────────────────────── */
genForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const req = {
    graph_id:         state.graphId,
    topic:            $('inputTopic').value.trim(),
    audience:         $('inputAudience').value.trim(),
    tone:             $('inputTone').value,
    num_slides:       parseInt($('inputSlides').value) || 6,
    user_preferences: $('inputPreferences').value.trim(),
  };
  if (!req.topic || !req.audience) return;

  const prefEcho = req.user_preferences
    ? `<br><span style="opacity:.75">↳ ${escHtml(req.user_preferences)}</span>`
    : '';
  addMessage('user', `<strong>${escHtml(req.topic)}</strong> · ${escHtml(req.audience)} · ${req.tone} · ${req.num_slides} slides${prefEcho}`);
  setLoading(true);

  try {
    switch (state.graphId) {
      case '1': await runBasic(req); break;
      case '2': await runConditional(req); break;
      case '3': await runHitl(req); break;
      case '4': await runTimeTravel(req); break;
      case '5': await runMemory(req); break;
      case '6': await runStreaming(req); break;
    }
  } catch (err) {
    addMessage('assistant', `<span style="color:#DC2626">Error: ${err.message}</span>`);
  } finally {
    setLoading(false);
  }
});

/* ── API helpers ────────────────────────────────────────────────────────── */
async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || res.statusText);
  }
  return res.json();
}

/* ── Graph 1 — Basic ────────────────────────────────────────────────────── */
function savedMsg(filename) {
  return filename ? ` · <code>presentations/${filename}</code>` : '';
}

async function runBasic(req) {
  addMessage('assistant', 'Running basic graph… parallel content + design → assemble → HTML → validate.');
  const data = await post('/api/generate', req);
  if (data.saved_as) renderPreview(data.saved_as);
  addMessage('assistant', `Done! <strong>${data.slides.length} slides</strong> generated.${savedMsg(data.saved_as)}`);
}

/* ── Graph 2 — Conditional ──────────────────────────────────────────────── */
async function runConditional(req) {
  const path = req.tone === 'technical' ? 'technical' : 'casual/creative';
  addMessage('assistant', `Conditional edge routing → <strong>${path}</strong> content generator.`);
  const data = await post('/api/generate', req);
  if (data.saved_as) renderPreview(data.saved_as);
  addMessage('assistant', `Done via <strong>${path}</strong> path! ${data.slides.length} slides.${savedMsg(data.saved_as)}`);
}

/* ── Graph 3 — HITL ─────────────────────────────────────────────────────── */
async function runHitl(req) {
  addMessage('assistant', 'Generating content + design… will pause for your review.');
  const data = await post('/api/hitl/start', req);
  state.threadId = data.thread_id;
  state.hitlData = { design_system: data.design_system, slides: data.slides };
  addMessage('assistant', 'Paused at <strong>Human Review</strong>. Edit the design and slides in the modal, then approve.');
  openHitlModal(data.design_system, data.slides);
}

/* ── Graph 4 — Time Travel ──────────────────────────────────────────────── */
async function runTimeTravel(req) {
  addMessage('assistant', 'Running with checkpointing. Every node saves a checkpoint — try <strong>Simulate Error</strong> after generation.');
  const data = await post('/api/time-travel/run', req);
  state.ttThreadId = data.thread_id;

  if (data.error) {
    state.ttError = data.error;
    addMessage('assistant', `Validation error: <code>${data.error}</code> — click <strong>Time Travel</strong> to replay from <code>assemble_outline</code>.`);
    renderTimeTravelControls();
    return;
  }

  state.ttError = null;
  if (data.saved_as) renderPreview(data.saved_as);
  addMessage('assistant', `Done! ${data.slides.length} slides. Use <strong>Simulate Error</strong> to demo time travel.${savedMsg(data.saved_as)}`);
  renderTimeTravelControls();
}

function renderTimeTravelControls() {
  graphControls.innerHTML = '';
  graphControls.classList.remove('hidden');

  if (state.ttThreadId && !state.ttError) {
    const chip = document.createElement('span');
    chip.className = 'status-chip chip-ok';
    chip.textContent = 'Checkpoint saved at assemble_outline';
    graphControls.appendChild(chip);

    const btn = document.createElement('button');
    btn.className = 'ctrl-btn ctrl-btn-amber';
    btn.textContent = 'Simulate Error';
    btn.onclick = () => {
      state.ttError = "HTML validation error — simulated";
      clearPreview();
      addMessage('assistant', 'Error simulated! Now click <strong>↩ Time Travel</strong> to replay from <code>assemble_outline</code>.');
      renderTimeTravelControls();
    };
    graphControls.appendChild(btn);
  }

  if (state.ttError) {
    const chip = document.createElement('span');
    chip.className = 'status-chip chip-error';
    chip.textContent = `Error: ${state.ttError}`;
    graphControls.appendChild(chip);

    if (state.ttThreadId) {
      const btn = document.createElement('button');
      btn.className = 'ctrl-btn ctrl-btn-green';
      btn.textContent = '↩ Time Travel → assemble_outline';
      btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = 'Travelling…';
        addMessage('assistant', 'Travelling back to <code>assemble_outline</code> checkpoint and regenerating JSX…');
        try {
          const data = await post('/api/time-travel/replay', { thread_id: state.ttThreadId });
          state.ttError = null;
          if (data.saved_as) renderPreview(data.saved_as);
          addMessage('assistant', `Time travel successful! Replayed from <code>assemble_outline</code>.${savedMsg(data.saved_as)}`);
          renderTimeTravelControls();
        } catch (err) {
          addMessage('assistant', `<span style="color:#DC2626">Replay failed: ${err.message}</span>`);
          btn.disabled = false;
          btn.textContent = '↩ Time Travel → assemble_outline';
        }
      };
      graphControls.appendChild(btn);
    }
  }

  if (!state.ttThreadId) {
    const hint = document.createElement('span');
    hint.className = 'status-chip chip-info';
    hint.textContent = 'Run the graph first to enable time travel';
    graphControls.appendChild(hint);
  }
}

/* ── Graph 5 — Memory ───────────────────────────────────────────────────── */
async function runMemory(req) {
  addMessage('assistant', 'Running with long-term memory. Past style preferences are loaded and saved.');
  const data = await post('/api/generate', req);
  if (data.saved_as) renderPreview(data.saved_as);
  if (data.memory_hint) {
    const m = data.memory_hint;
    addMessage('assistant',
      `Done! Style saved to memory: <code>${m.font_family}</code> · <code>${m.layout_style}</code> · accent <code>${m.accent}</code>${savedMsg(data.saved_as)}`
    );
    renderMemoryControls(data.memory_hint);
  } else {
    addMessage('assistant', `Done! ${data.slides.length} slides. Style saved for next time.${savedMsg(data.saved_as)}`);
  }
}

function renderMemoryControls(pref) {
  graphControls.innerHTML = '';
  graphControls.classList.remove('hidden');
  const chip = document.createElement('span');
  chip.className = 'status-chip chip-purple';
  chip.innerHTML = `Memory: <strong>${pref.font_family}</strong> · <strong>${pref.layout_style}</strong> · accent <span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:${pref.accent};vertical-align:middle;margin-left:4px"></span>`;
  graphControls.appendChild(chip);
}

/* ── Graph 6 — Streaming ────────────────────────────────────────────────── */
async function runStreaming(req) {
  addMessage('assistant', 'Streaming started — watch the chat for live progress and the preview for the result.');
  streamProgress.innerHTML = '';
  streamProgress.classList.remove('hidden');
  state.streamNodes = {};

  const response = await fetch('/api/generate/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!response.ok) throw new Error('Stream request failed');

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      let evt;
      try { evt = JSON.parse(line.slice(6)); } catch { continue; }
      handleStreamEvent(evt);
    }
  }
}

function handleStreamEvent(evt) {
  switch (evt.type) {
    case 'progress': {
      const { node, status, label } = evt;
      updateNodePill(node, status);
      if (status === 'running') {
        addMessage('assistant', `<strong>${node}</strong> — ${label}`);
      } else if (status === 'done') {
        addMessage('assistant', `✓ <strong>${node}</strong> — ${label}`);
      }
      break;
    }
    case 'node_done': {
      updateNodePill(evt.node, 'done');
      break;
    }
    case 'done': {
      if (evt.saved_as) renderPreview(evt.saved_as);
      addMessage('assistant', `Streaming complete! Presentation ready.${savedMsg(evt.saved_as)}`);
      break;
    }
    case 'error': {
      addMessage('assistant', `<span style="color:#DC2626">Stream error: ${evt.message}</span>`);
      break;
    }
    case 'end': {
      streamProgress.classList.add('hidden');
      break;
    }
  }
}

function updateNodePill(node, status) {
  let pill = streamProgress.querySelector(`[data-node="${node}"]`);
  if (!pill) {
    pill = document.createElement('span');
    pill.className = 'node-pill';
    pill.dataset.node = node;
    streamProgress.appendChild(pill);
  }
  pill.className = `node-pill ${status}`;
  pill.innerHTML = status === 'running'
    ? `⟳ ${node}`
    : `✓ ${node}`;
}

/* ── HITL Modal ─────────────────────────────────────────────────────────── */
function openHitlModal(designSystem, slides) {
  state.hitlData = { design_system: designSystem, slides };
  renderDesignTab(designSystem);
  renderSlidesTab(slides);
  hitlOverlay.classList.remove('hidden');
}

function closeHitlModal() {
  hitlOverlay.classList.add('hidden');
}

hitlClose.addEventListener('click', closeHitlModal);
hitlCancel.addEventListener('click', closeHitlModal);
hitlOverlay.addEventListener('click', (e) => {
  if (e.target === hitlOverlay) closeHitlModal();
});

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
    btn.classList.add('active');
    $(`tab${btn.dataset.tab.charAt(0).toUpperCase() + btn.dataset.tab.slice(1)}`).classList.remove('hidden');
  });
});

function renderDesignTab(ds) {
  const c = ds.colors || {};
  const t = ds.typography || {};

  tabDesign.innerHTML = `
    <div class="ds-section">
      <h3>Colors</h3>
      <div class="color-grid">
        ${colorField('Primary BG',    'ds_primary_bg',    c.primary_bg    || '#0a0e27')}
        ${colorField('Secondary BG',  'ds_secondary_bg',  c.secondary_bg  || '#1a2040')}
        ${colorField('Accent',        'ds_accent',        c.accent        || '#4f8ef7')}
        ${colorField('Text Primary',  'ds_text_primary',  c.text_primary  || '#ffffff')}
        ${colorField('Text Secondary','ds_text_secondary',c.text_secondary|| '#8892b0')}
      </div>
    </div>
    <div class="ds-section">
      <h3>Typography</h3>
      <div class="ds-row">
        <div class="form-group">
          <label class="form-label">Font Family</label>
          <select class="form-input" id="ds_font_family">
            ${['Inter','Space Grotesk','Roboto Mono','Playfair Display'].map(f =>
              `<option value="${f}" ${f === t.font_family ? 'selected' : ''}>${f}</option>`
            ).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Layout Style</label>
          <select class="form-input" id="ds_layout_style">
            ${['minimal','bold','editorial'].map(s =>
              `<option value="${s}" ${s === ds.layout_style ? 'selected' : ''}>${s}</option>`
            ).join('')}
          </select>
        </div>
      </div>
      <div class="ds-row">
        <div class="form-group">
          <label class="form-label">Heading Size (px, min 48)</label>
          <input type="number" class="form-input" id="ds_heading_size" value="${t.heading_size || 64}" min="48" max="120"/>
        </div>
        <div class="form-group">
          <label class="form-label">Body Size (px, min 24)</label>
          <input type="number" class="form-input" id="ds_body_size" value="${t.body_size || 28}" min="24" max="72"/>
        </div>
      </div>
    </div>
  `;
}

function colorField(label, id, value) {
  return `
    <div class="color-field">
      <label for="${id}">${label}</label>
      <input type="color" id="${id}" value="${value}"/>
    </div>
  `;
}

function renderSlidesTab(slides) {
  tabSlides.innerHTML = slides.map((slide, i) => `
    <div class="slide-card">
      <div class="slide-card-header" onclick="toggleSlideCard(${i})">
        <span>Slide ${i + 1}: ${escHtml(slide.title)}</span>
        <span id="card-arrow-${i}">▼</span>
      </div>
      <div class="slide-card-body ${i === 0 ? '' : 'hidden'}" id="slide-card-body-${i}">
        <div class="form-group">
          <label class="form-label">Title</label>
          <input class="form-input" id="slide_title_${i}" type="text" value="${escHtml(slide.title)}"/>
        </div>
        <div class="form-group">
          <label class="form-label">Layout</label>
          <select class="form-input" id="slide_layout_${i}">
            ${['hero','bullets','two-column','quote'].map(l =>
              `<option value="${l}" ${l === slide.layout_hint ? 'selected' : ''}>${l}</option>`
            ).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Content (one item per line)</label>
          <textarea class="form-input" id="slide_content_${i}" rows="4">${(slide.content || []).join('\n')}</textarea>
        </div>
      </div>
    </div>
  `).join('');
}

function toggleSlideCard(i) {
  const body  = $(`slide-card-body-${i}`);
  const arrow = $(`card-arrow-${i}`);
  body.classList.toggle('hidden');
  arrow.textContent = body.classList.contains('hidden') ? '▼' : '▲';
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

hitlApprove.addEventListener('click', async () => {
  if (!state.threadId || !state.hitlData) return;

  const originalDs = state.hitlData.design_system;
  const originalT  = originalDs.typography || {};

  const editedDesign = {
    colors: {
      primary_bg:    $('ds_primary_bg')?.value    || originalDs.colors?.primary_bg,
      secondary_bg:  $('ds_secondary_bg')?.value  || originalDs.colors?.secondary_bg,
      accent:        $('ds_accent')?.value         || originalDs.colors?.accent,
      text_primary:  $('ds_text_primary')?.value   || originalDs.colors?.text_primary,
      text_secondary:$('ds_text_secondary')?.value || originalDs.colors?.text_secondary,
    },
    typography: {
      font_family:    $('ds_font_family')?.value  || originalT.font_family,
      layout_style:   $('ds_layout_style')?.value,
      heading_size:   parseInt($('ds_heading_size')?.value) || originalT.heading_size,
      body_size:      parseInt($('ds_body_size')?.value)    || originalT.body_size,
      weight_heading: originalT.weight_heading || 700,
      weight_body:    originalT.weight_body    || 400,
    },
    layout_style: $('ds_layout_style')?.value || originalDs.layout_style,
  };

  const editedSlides = state.hitlData.slides.map((slide, i) => ({
    ...slide,
    title:       $(`slide_title_${i}`)?.value   || slide.title,
    layout_hint: $(`slide_layout_${i}`)?.value  || slide.layout_hint,
    content:     ($(`slide_content_${i}`)?.value || '').split('\n').map(l => l.trim()).filter(Boolean),
  }));

  closeHitlModal();
  addMessage('assistant', 'Review approved — generating HTML with your edits…');
  setLoading(true);

  try {
    const data = await post('/api/hitl/resume', {
      thread_id:     state.threadId,
      design_system: editedDesign,
      slides:        editedSlides,
    });
    if (data.saved_as) renderPreview(data.saved_as);
    addMessage('assistant', `Presentation generated with your customizations! ${data.slides.length} slides.${savedMsg(data.saved_as)}`);
  } catch (err) {
    addMessage('assistant', `<span style="color:#DC2626">Resume failed: ${err.message}</span>`);
  } finally {
    setLoading(false);
  }
});

/* ── Bootstrap ──────────────────────────────────────────────────────────── */
updateBadge();
updateControls();
loadPresentationsList();

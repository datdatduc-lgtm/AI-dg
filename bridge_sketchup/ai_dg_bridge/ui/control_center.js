(function () {
  'use strict';

  const state = {
    selectedTab: 'codex',
    runtime: null,
    pipeline: null,
    source: null,
    developerMode: false,
    hostEvents: [],
    streamNodes: {},
    agents: {
      codex: { sessionId: null, threadId: null, model: null, running: false },
      cline: { sessionId: null, threadId: null, model: null, running: false }
    }
  };

  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  function ruby(name, payload) {
    if (window.sketchup && typeof window.sketchup[name] === 'function') {
      window.sketchup[name](JSON.stringify(payload || {}));
      return true;
    }
    return false;
  }

  function request(action, data) {
    return ruby('ai_dg_action', { action: action, data: data || {} });
  }

  function json(value) {
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }

  function activeBackend() {
    return state.selectedTab === 'cline' ? 'cline' : 'codex';
  }

  function documentKey() {
    const path = state.runtime && (state.runtime.model_path || state.runtime.modelPath);
    return String(path || 'untitled') + '|' + String(state.source?.project_root || 'E:/AI-DG');
  }

  function projectRoot() {
    return String(state.source?.project_root || 'E:/AI-DG');
  }

  function addMessage(backend, role, text, meta) {
    const history = $(backend + '-history');
    if (!history || !text) return;
    const item = document.createElement('div');
    item.className = 'chat-msg ' + role;
    item.innerHTML = '<div class="chat-body">' + esc(text) + '</div><div class="chat-meta">' + esc(meta || role) + '</div>';
    history.appendChild(item);
    while (history.children.length > 200) history.removeChild(history.firstChild);
    history.scrollTop = history.scrollHeight;
  }

  function setNotice(backend, text, tone) {
    const node = $(backend + '-readiness');
    if (!node) return;
    node.textContent = text;
    node.className = 'notice' + (tone ? ' ' + tone : '');
  }

  function setAgentState(backend, text, tone) {
    const node = $(backend + '-state');
    if (!node) return;
    node.textContent = text;
    node.className = 'status-pill' + (tone ? ' ' + tone : '');
    state.agents[backend].running = /RUNNING|CANCELLING|APPROVAL/i.test(text);
  }

  function setSession(backend, data) {
    const agent = state.agents[backend];
    if (!agent || !data) return;
    agent.sessionId = data.session_id || data.sessionId || agent.sessionId;
    agent.threadId = data.thread_id || data.threadId || agent.threadId;
    const sessionNode = $(backend + '-session');
    if (sessionNode) sessionNode.textContent = 'Session: ' + (agent.sessionId || agent.threadId || '—');
    const models = data.models || data.model || data.native?.models;
    if (models && typeof models === 'object') {
      const first = Array.isArray(models) ? models[0] : (models.currentModelId || models.current_model_id || models.model);
      if (first) agent.model = typeof first === 'object' ? (first.id || first.model || '') : first;
    }
    const modelNode = $(backend + '-model');
    if (modelNode && agent.model) modelNode.textContent = 'Model: ' + agent.model;
  }

  function flattenText(value, key, out) {
    out = out || [];
    if (value == null) return out;
    if (typeof value === 'string') {
      if (/^(text|delta|content|message|explanation|reason|summary)$/i.test(String(key || '')) || !key) out.push(value);
      return out;
    }
    if (Array.isArray(value)) {
      value.slice(0, 20).forEach(item => flattenText(item, key, out));
      return out;
    }
    if (typeof value === 'object') {
      Object.keys(value).forEach(name => {
        const child = value[name];
        if (/^(text|delta|message|explanation|reason|summary)$/i.test(name) && typeof child === 'string') out.push(child);
        else if (/^(content|update|item|error)$/i.test(name)) flattenText(child, name, out);
      });
    }
    return out;
  }

  function eventText(event) {
    const data = event && event.data ? event.data : {};
    const pieces = flattenText(data, '', []);
    return pieces.join('');
  }

  function approvalResult(nativeMethod, approved) {
    if (!approved) return null;
    if (/request_permission/i.test(nativeMethod)) return { outcome: 'allow_once' };
    if (/permissions\/requestApproval/i.test(nativeMethod)) return { permissions: {}, scope: 'turn' };
    if (/elicitation\/request/i.test(nativeMethod)) return { action: 'accept', content: {} };
    return { decision: 'accept' };
  }

  function renderApproval(backend, event) {
    const data = event.data || {};
    const requestId = data.request_id;
    const method = data.method || 'approval';
    const params = data.params || {};
    const history = $(backend + '-history');
    if (!history || !requestId) return;
    const item = document.createElement('div');
    item.className = 'chat-msg approval';
    const reason = params.reason || params.command || params.cwd || 'Runtime yêu cầu quyền tiếp tục.';
    item.innerHTML = '<div class="chat-body">' + esc(reason) + '</div><div class="chat-meta">APPROVAL · ' + esc(method) + '</div><div class="chat-input-footer"><span>Không tự động chấp thuận</span><div><button class="secondary approval-deny">Từ chối</button><button class="primary approval-accept">Cho phép</button></div></div>';
    item.querySelector('.approval-accept').addEventListener('click', () => {
      request('agent_approval', { backend: backend, request_id: requestId, method: method, approved: true, result: approvalResult(method, true) });
      item.remove();
    });
    item.querySelector('.approval-deny').addEventListener('click', () => {
      request('agent_approval', { backend: backend, request_id: requestId, method: method, approved: false });
      item.remove();
    });
    history.appendChild(item);
    history.scrollTop = history.scrollHeight;
  }

  function handleAgentEvent(message) {
    const backend = message.backend;
    if (!state.agents[backend]) return;
    const event = String(message.event || '');
    const data = message.data || {};
    state.hostEvents.push({ backend: backend, event: event, session_id: message.session_id, data: data });
    state.hostEvents = state.hostEvents.slice(-200);
    if ($('developer-events') && state.developerMode) $('developer-events').textContent = json(state.hostEvents);
    if (event === 'turn/started') state.streamNodes[backend] = {};
    if (event === 'runtime/ready') {
      setAgentState(backend, 'RUNTIME READY', 'good');
      setNotice(backend, backend === 'codex' ? 'Codex App Server đã handshake.' : 'Cline ACP đã handshake.', 'good');
    } else if (event === 'runtime/exited') {
      setAgentState(backend, 'RUNTIME STOPPED', 'bad');
      setNotice(backend, 'Runtime đã dừng; kiểm tra Developer Diagnostics.', 'bad');
    } else if (event === 'install/started') {
      setAgentState(backend, 'INSTALLING', '');
      setNotice(backend, 'Đang cài Cline tự động. SketchUp vẫn hoạt động bình thường.', '');
    } else if (event === 'install/completed') {
      setAgentState(backend, 'READY', 'good');
      setNotice(backend, 'Cline đã cài xong. Bấm “Mở session”.', 'good');
    } else if (event === 'install/failed') {
      setAgentState(backend, 'INSTALL FAILED', 'bad');
      setNotice(backend, 'Không cài được Cline: ' + (data.error || 'kiểm tra npm và mạng'), 'bad');
    } else if (event === 'server/request') {
      setAgentState(backend, 'WAITING APPROVAL', '');
      renderApproval(backend, message);
    } else if (/turn\/(started|completed|failed|interrupted|aborted)/.test(event)) {
      if (/completed|failed|interrupted|aborted/.test(event)) {
        setAgentState(backend, /failed/.test(event) ? 'FAILED' : 'READY', /failed/.test(event) ? 'bad' : 'good');
        setNotice(backend, /failed/.test(event) ? 'Turn thất bại; lỗi đã được giữ nguyên từ runtime.' : 'Turn hoàn tất.', /failed/.test(event) ? 'bad' : 'good');
      } else setAgentState(backend, 'RUNNING', '');
    }
    if (/delta|agent_message_chunk|agent_message|plan\/updated|error/i.test(event) || (event === 'session/update' && data.update?.sessionUpdate === 'agent_message_chunk')) {
      const text = event === 'error' ? (data.error?.message || data.message || 'Runtime error') : eventText(message);
      if (text) {
        const streamId = data.itemId || data.item_id || (event === 'session/update' ? 'acp-message' : null);
        if (streamId) {
          const nodes = state.streamNodes[backend] || (state.streamNodes[backend] = {});
          if (!nodes[streamId]) {
            addMessage(backend, 'agent', text, backend.toUpperCase());
            nodes[streamId] = $(backend + '-history').lastElementChild.querySelector('.chat-body');
          } else nodes[streamId].textContent += text;
        } else addMessage(backend, 'agent', text, backend.toUpperCase());
      }
    }
    if (event === 'session/resume_failed') addMessage(backend, 'system', 'Resume thất bại; liên kết phiên đã được giữ lại. ' + (data.error || ''), 'SESSION');
  }

  function handleAgentResponse(message) {
    const response = message.data || {};
    if (response.status === 'error' || message.status === 'error') {
      const rawDetail = response.detail || response.error || message.error || 'Unknown runtime error';
      const detail = typeof rawDetail === 'object' ? (rawDetail.message || json(rawDetail)) : rawDetail;
      const backend = response.data?.backend || response.backend || activeBackend();
      setAgentState(backend, 'ERROR', 'bad');
      setNotice(backend, 'Runtime error: ' + detail, 'bad');
      addMessage(backend, 'system', detail, 'RUNTIME ERROR');
      return;
    }
    const data = response.data || response;
    const backend = data.backend || response.backend;
    if (backend && state.agents[backend]) {
      setSession(backend, data);
      if (response.method === 'session/open' || response.method === 'session/resume') setAgentState(backend, 'SESSION READY', 'good');
      if (data.turn_id) setAgentState(backend, 'RUNNING', '');
      else if (data.session_id || data.thread_id || data.sessionId || data.threadId) setAgentState(backend, 'SESSION READY', 'good');
      if (data.cancelled || data.native?.stopReason) setAgentState(backend, 'READY', 'good');
    }
  }

  function renderRuntime(data) {
    if (!data) return;
    state.runtime = data;
    const mode = String(data.access_mode || data.accessMode || 'read_only');
    $('mode-badge').textContent = mode === 'write_enabled' ? 'WRITE ENABLED' : 'READ ONLY';
    $('mode-badge').style.color = mode === 'write_enabled' ? 'var(--warn)' : 'var(--good)';
    $('mode-toggle').textContent = mode === 'write_enabled' ? 'Tắt ghi model' : 'Bật ghi model';
    const host = data.agent_host || {};
    const codex = host.codex || {};
    const cline = host.cline || {};
    $('settings-host').textContent = host.host || '—';
    $('settings-codex').textContent = codex.alive ? 'Đang chạy' : (codex.available ? 'Sẵn sàng' : 'Chưa có');
    $('settings-cline').textContent = cline.alive ? 'Đang chạy' : (cline.install_state || (cline.available ? 'Sẵn sàng' : 'Chưa có'));
    $('settings-bridge').textContent = data.bridge_status || 'UNKNOWN';
    $('settings-instance').textContent = (data.model_title || 'Untitled') + (data.instance_id ? ' · ' + data.instance_id : '');
    $('footer-status').textContent = data.bridge_status === 'ONLINE' ? 'Bridge online' : 'Bridge ' + (data.bridge_status || 'đang khởi động');
    $('footer-dot').className = 'dot ' + (data.bridge_status === 'ONLINE' ? 'good' : 'bad');
    if (data.developer_mode !== undefined) applyDeveloperMode({ developer_mode: data.developer_mode });
    if (state.source?.project_root) $('settings-project').textContent = state.source.project_root;
  }

  function renderPipeline(data) {
    state.pipeline = data || {};
    const cards = $('drawing-cards');
    const builds = $('build-cards');
    const p = data || {};
    const rows = [['Trạng thái', p.status || 'NOT_RUN'], ['Gate', p.gate_status || '—'], ['Gói', p.package_count || 0], ['Review', p.review_status || '—']];
    const html = rows.map(row => '<div class="metric"><span>' + esc(row[0]) + '</span><strong>' + esc(row[1]) + '</strong></div>').join('');
    if (cards) cards.innerHTML = html;
    if (builds) builds.innerHTML = html;
    if ($('pipeline-data')) $('pipeline-data').textContent = json(data);
    if ($('build-list')) {
      const operations = Array(p.build_operations).concat(Array(p.blocked_items)).filter(Boolean);
      $('build-list').innerHTML = operations.length ? operations.slice(0, 100).map(item => '<div class="trace-row"><strong>' + esc(item.operation || item.type || item.id || 'Item') + '</strong><small>' + esc(item.reason || item.status || JSON.stringify(item)) + '</small></div>').join('') : '<div class="empty">Chưa có build plan.</div>';
    }
  }

  function renderSource(data) {
    state.source = data || {};
    const output = $('source-data');
    if (output) output.textContent = json(data);
    if ($('settings-project')) $('settings-project').textContent = data?.project_root || 'Chưa chọn';
  }

  function applyDeveloperMode(data) {
    state.developerMode = Boolean(data && data.developer_mode);
    document.querySelectorAll('.developer-only').forEach(node => { node.hidden = !state.developerMode; });
    if (!state.developerMode && state.selectedTab === 'developer') selectTab('codex');
  }

  function selectTab(tab) {
    if (tab === 'developer' && !state.developerMode) tab = 'codex';
    state.selectedTab = tab;
    document.querySelectorAll('.tab').forEach(node => node.classList.toggle('active', node.dataset.tab === tab));
    document.querySelectorAll('.panel').forEach(node => node.classList.toggle('active', node.id === 'panel-' + tab));
    if (tab === 'drawings' || tab === 'build') {
      request('pipeline_status');
      request('source_folder_status');
    }
    if (tab === 'settings') request('agent_host_status');
    if (tab === 'developer') {
      request('get_code_view');
      request('get_trace', { limit: 200 });
      request('plugin_diagnostics');
    }
  }

  function sendAgent(backend) {
    const input = $(backend + '-text');
    if (!input) return;
    const text = input.value.trim();
    if (!text || state.agents[backend].running) return;
    state.streamNodes[backend] = {};
    addMessage(backend, 'user', text, 'USER');
    input.value = '';
    setAgentState(backend, 'RUNNING', '');
    setNotice(backend, 'Đã gửi tới ' + (backend === 'codex' ? 'Codex App Server' : 'Cline ACP') + '; đang chờ event thật…', '');
    request('agent_turn_start', { backend: backend, text: text, cwd: projectRoot(), document_key: documentKey() });
  }

  function openAgent(backend, resume) {
    if (state.agents[backend].running) return;
    if (resume) {
      $(backend + '-history').replaceChildren();
      state.streamNodes[backend] = {};
    }
    setAgentState(backend, resume ? 'RESUMING' : 'OPENING', '');
    setNotice(backend, resume ? 'Đang resume session thật…' : 'Đang mở runtime/session thật…', '');
    request(resume ? 'agent_session_resume' : 'agent_session_open', { backend: backend, cwd: projectRoot(), document_key: documentKey() });
  }

  window.aiDgReceive = function (message) {
    if (!message) return;
    if (message.action === 'runtime') { renderRuntime(message.data); return; }
    if (message.action === 'agent_event') { handleAgentEvent(message.data || {}); return; }
    if (message.action === 'agent_response') { handleAgentResponse(message); return; }
    if (message.action === 'pipeline_status') { renderPipeline(message.data || message); return; }
    if (message.action === 'source_folder_status' || message.action === 'source_folder_select') { renderSource(message.data || message); return; }
    if (message.action === 'get_code_view') {
      if ($('developer-runtime')) $('developer-runtime').textContent = json(message.data || message);
      return;
    }
    if (message.action === 'get_trace') {
      if ($('developer-events')) $('developer-events').textContent = json(message.data || message);
      return;
    }
    if (message.action === 'plugin_diagnostics') {
      if ($('developer-host')) $('developer-host').textContent = json(message.data || message);
      return;
    }
    if (message.status === 'error') addMessage(activeBackend(), 'system', message.error || 'Bridge error', 'BRIDGE ERROR');
  };

  document.querySelectorAll('.tab').forEach(node => node.addEventListener('click', () => selectTab(node.dataset.tab)));
  document.querySelectorAll('[data-agent-open]').forEach(node => node.addEventListener('click', () => openAgent(node.dataset.agentOpen, false)));
  document.querySelectorAll('[data-agent-resume]').forEach(node => node.addEventListener('click', () => openAgent(node.dataset.agentResume, true)));
  document.querySelectorAll('[data-agent-send]').forEach(node => node.addEventListener('click', () => sendAgent(node.dataset.agentSend)));
  document.querySelectorAll('[data-agent-cancel]').forEach(node => node.addEventListener('click', () => request('agent_turn_cancel', { backend: node.dataset.agentCancel, document_key: documentKey(), cwd: projectRoot() })));
  document.querySelectorAll('textarea').forEach(node => node.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendAgent(node.id.replace(/-text$/, ''));
    }
  }));
  $('mode-toggle').addEventListener('click', () => {
    const current = $('mode-badge').textContent === 'WRITE ENABLED' ? 'write_enabled' : 'read_only';
    request('set_mode', { mode: current === 'write_enabled' ? 'read_only' : 'write_enabled' });
  });
  const clineMode = document.createElement('select');
  clineMode.setAttribute('aria-label', 'Chế độ Cline');
  clineMode.innerHTML = '<option value="plan">Plan</option><option value="act">Act</option>';
  clineMode.addEventListener('change', () => request('agent_set_mode', {backend: 'cline', mode_id: clineMode.value, cwd: projectRoot()}));
  $('panel-cline').querySelector('.chat-toolbar').appendChild(clineMode);
  ['codex-session', 'cline-session'].forEach(id => $(id).classList.add('developer-only'));
  $('source-select').addEventListener('click', () => request('source_folder_select'));
  $('settings-source-select').addEventListener('click', () => request('source_folder_select'));
  $('source-refresh').addEventListener('click', () => { request('source_folder_status'); request('pipeline_status'); });
  $('build-refresh').addEventListener('click', () => request('pipeline_status'));
  $('developer-refresh').addEventListener('click', () => { request('agent_host_status'); request('get_code_view'); request('get_trace', { limit: 200 }); request('plugin_diagnostics'); });
  $('reload-runtime').addEventListener('click', () => request('reload_runtime_source'));

  applyDeveloperMode({ developer_mode: false });
  if (ruby('ai_dg_ready', {})) {
    request('agent_host_status');
    request('source_folder_status');
    request('pipeline_status');
    selectTab('codex');
  }
}());

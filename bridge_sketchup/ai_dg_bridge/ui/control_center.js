(function () {
  'use strict';

  const state = {
    runtime: null,
    trace: [],
    selectedTab: 'runtime',
    bridgeTools: [],
    skills: [],
    plugins: [],
    selectedEntityId: null,
    developerMode: false,
    pipeline: null,
    providerAudit: {},
    modelStatus: {},
    agentBackend: {}
  };

  const fallbackTools = [
    ['sketchup_ping', 'sketchup.read', 'LOW'],
    ['sketchup_health', 'sketchup.read', 'LOW'],
    ['sketchup_get_runtime_state', 'runtime.read', 'LOW'],
    ['sketchup_get_model_summary', 'sketchup.read', 'LOW'],
    ['sketchup_get_selection', 'sketchup.read', 'LOW'],
    ['sketchup_get_entity', 'sketchup.read', 'LOW'],
    ['sketchup_get_hierarchy', 'sketchup.read', 'LOW'],
    ['sketchup_list_components', 'sketchup.read', 'LOW'],
    ['sketchup_list_materials', 'sketchup.read', 'LOW'],
    ['sketchup_list_tags', 'sketchup.read', 'LOW'],
    ['sketchup_list_scenes', 'sketchup.read', 'LOW'],
    ['sketchup_get_camera', 'sketchup.read', 'LOW'],
    ['sketchup_get_bounds', 'sketchup.read', 'LOW'],
    ['sketchup_get_trace', 'runtime.read', 'LOW'],
    ['sketchup_capture_viewport', 'filesystem.write', 'MEDIUM'],
    ['sketchup_create_box', 'sketchup.write', 'MEDIUM'],
    ['sketchup_reload_runtime', 'runtime.reload', 'MEDIUM'],
  ];

  const $ = id => document.getElementById(id);

  const developerTabs = new Set(['flow', 'sequence', 'tool-calls', 'agent-steps', 'errors', 'tools', 'skills', 'plugins', 'model', 'developer', 'logs']);
  const developerSettingGroups = new Set(['tools', 'skills', 'plugins', 'runtime', 'permissions', 'developer', 'logs', 'recovery']);

  function applyDeveloperMode(data) {
    state.developerMode = Boolean(data && data.developer_mode);
    document.body.dataset.developerMode = state.developerMode ? '1' : '0';
    document.querySelectorAll('.tab[data-tab]').forEach(button => {
      button.hidden = !state.developerMode && developerTabs.has(button.dataset.tab);
    });
    document.querySelectorAll('.panel[id^="panel-"]').forEach(panel => {
      const tab = panel.id.replace('panel-', '');
      panel.hidden = !state.developerMode && developerTabs.has(tab);
    });
    document.querySelectorAll('.settings-tab[data-settings-group]').forEach(button => {
      button.hidden = !state.developerMode && developerSettingGroups.has(button.dataset.settingsGroup);
    });
    if (!state.developerMode && developerTabs.has(state.selectedTab)) {
      state.selectedTab = 'runtime';
      document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item.dataset.tab === 'runtime'));
      document.querySelectorAll('.panel').forEach(item => item.classList.toggle('active', item.id === 'panel-runtime'));
    }
  }

  function initializeSettingsTabs() {
    const grid = document.querySelector('.settings-grid');
    if (!grid || grid.dataset.tabsReady === '1') return;

    const groups = [
      ['general', 'Chung'],
      ['ai', 'AI'],
      ['provider', '9Router'],
      ['model', 'Model'],
      ['mcp', 'MCP'],
      ['sketchup', 'SketchUp'],
      ['agent', 'Agent'],
      ['tools', 'Tools'],
      ['skills', 'Skills'],
      ['plugins', 'Plugins'],
      ['runtime', 'Runtime'],
      ['permissions', 'Permissions'],
      ['developer', 'Developer'],
      ['logs', 'Logs'],
      ['recovery', 'Recovery']
    ];
    const tabs = document.createElement('div');
    tabs.className = 'settings-tabs';
    tabs.setAttribute('role', 'tablist');
    tabs.innerHTML = groups.map(([id, label], index) =>
      '<button class="settings-tab' + (index === 0 ? ' active' : '') + '" data-settings-group="' + id +
      '" role="tab" aria-selected="' + (index === 0 ? 'true' : 'false') + '">' + esc(label) + '</button>'
    ).join('');
    grid.parentNode.insertBefore(tabs, grid);

    const cards = Array.from(grid.querySelectorAll('.card'));
    const title = card => (card.querySelector('h2')?.textContent || '').trim();
    const matches = (card, group) => {
      const value = title(card);
      if (group === 'general') return value === 'Chung';
      if (group === 'ai' || group === 'agent') return value === 'AI / Agent';
      if (group === 'provider' || group === 'recovery') return value === '9Router / Provider';
      if (group === 'model') return value === 'Model manager';
      if (group === 'mcp') return value === 'MCP';
      if (group === 'sketchup') return value === 'SketchUp';
      if (group === 'tools' || group === 'skills' || group === 'plugins') return value === 'Tools / Skills / Plugins';
      if (group === 'runtime' || group === 'logs' || group === 'developer') return value === 'Runtime / Logs / Developer';
      if (group === 'permissions') return value === 'Permissions';
      return true;
    };
    const activate = group => {
      tabs.querySelectorAll('.settings-tab').forEach(tab => {
        const active = tab.dataset.settingsGroup === group;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      cards.forEach(card => { card.hidden = !matches(card, group); });
    };
    tabs.querySelectorAll('.settings-tab').forEach(tab =>
      tab.addEventListener('click', () => activate(tab.dataset.settingsGroup))
    );
    grid.dataset.tabsReady = '1';
    activate('general');
  }

  function openSettingsGroup(group) {
    const settingsTab = document.querySelector('.tab[data-tab="settings"]');
    if (settingsTab) settingsTab.click();
    const groupTab = document.querySelector('.settings-tab[data-settings-group="' + group + '"]');
    if (groupTab) groupTab.click();
  }

  function initializeChatNavigationControls() {
    const providerButton = $('chat-open-settings');
    const toolbar = providerButton?.parentElement;
    if (!toolbar || $('chat-open-model-settings')) return;

    const modelButton = document.createElement('button');
    modelButton.id = 'chat-open-model-settings';
    modelButton.className = 'secondary';
    modelButton.textContent = 'Chọn model';
    modelButton.title = 'Mở Model Manager để chọn Canonical model ID';
    modelButton.addEventListener('click', () => openSettingsGroup('model'));
    providerButton.insertAdjacentElement('afterend', modelButton);
  }

  function initializeAgentBackendControls() {
    const card = Array.from(document.querySelectorAll('.card')).find(item => (item.querySelector('h2')?.textContent || '').trim() === 'AI / Agent');
    if (!card || $('agent-backend-form')) return;
    const form = document.createElement('div');
    form.id = 'agent-backend-form';
    form.className = 'provider-config-form';
    form.innerHTML = '<div class="setting-row"><label for="agent-backend">Chat backend</label><select id="agent-backend"><option value="9router">9Router (OpenAI-compatible)</option><option value="codex_cli">Codex CLI (local)</option></select></div>' +
      '<div class="setting-row"><span>Backend status</span><strong id="agent-backend-status">NOT_QUERIED</strong></div>' +
      '<div class="head-actions"><button id="agent-backend-save" class="secondary">Lưu backend</button><button id="agent-backend-network-toggle" class="secondary">Cho phép Codex CLI</button></div>';
    card.appendChild(form);
    $('agent-backend-save').addEventListener('click', () => request('agent_backend_select', { backend: $('agent-backend').value }));
    $('agent-backend-network-toggle').addEventListener('click', () => {
      const enabled = $('agent-backend-network-toggle').dataset.enabled !== 'true';
      if (enabled && !window.confirm('Cho phép Codex CLI thực hiện external turn bằng sandbox read-only cho đến khi tắt?')) return;
      request(enabled ? 'codex_network_enable' : 'codex_network_disable');
    });
  }

  function initializeProviderActions() {
    const anchor = $('provider-audit');
    const container = anchor?.parentElement;
    if (!container || container.dataset.actionsReady === '1') return;
    const providerCard = anchor.closest('.card');
    if (providerCard && !$('provider-config-form')) {
      const form = document.createElement('div');
      form.id = 'provider-config-form';
      form.className = 'provider-config-form';
      form.innerHTML = '<div class="setting-row"><label for="provider-name-input">Provider Name</label><input id="provider-name-input" class="setting-input" value="9Router" autocomplete="organization"></div>' +
        '<div class="setting-row"><label for="provider-type">Provider Type</label><select id="provider-type"><option value="9router">9Router</option><option value="openai_compatible">OpenAI-compatible</option><option value="openrouter_compatible">OpenRouter-compatible</option><option value="custom_compatible">Custom-compatible</option></select></div>' +
        '<div class="setting-row"><label for="provider-base-url">Base URL</label><input id="provider-base-url" class="setting-input" placeholder="https://provider.example/v1" autocomplete="url"></div>' +
        '<div class="setting-row"><label for="provider-api-key">API key</label><input id="provider-api-key" class="setting-input" type="password" placeholder="Nhập key mới; để trống để giữ key hiện tại" autocomplete="new-password"></div>' +
        '<div class="setting-row"><span>Network permission</span><strong id="provider-network-status">REQUIRES_EXPLICIT_ENABLE</strong></div>' +
        '<div class="head-actions"><button id="provider-save" class="primary">Lưu provider</button><button id="provider-network-toggle" class="secondary">Cho phép gọi provider</button></div>';
      providerCard.insertBefore(form, container);
    }
    [
      ['provider-test', 'Test (opt-in)', 'provider_test'],
      ['provider-sync', 'Sync Models (opt-in)', 'provider_sync'],
      ['provider-disconnect', 'Disconnect', 'provider_disconnect']
    ].forEach(([id, label, action]) => {
      if ($(id)) return;
      const button = document.createElement('button');
      button.id = id;
      button.className = 'secondary';
      button.textContent = label;
      button.title = action === 'provider_disconnect'
        ? 'Ngắt trạng thái local; không chạm network.'
        : 'Chỉ chạy khi user bật rõ AI_DG_ALLOW_PROVIDER_TEST=1 cho MCP server.';
       button.addEventListener('click', () => request(action, action === 'provider_test' ? { model: $('model-id')?.value.trim() || '', prompt: 'Trả lời duy nhất: OK' } : {}));
      container.insertBefore(button, $('provider-refresh'));
    });
    $('provider-save')?.addEventListener('click', () => {
      const key = $('provider-api-key')?.value || '';
      request('provider_configure', {
        provider_name: $('provider-name-input')?.value.trim() || '',
        provider_type: $('provider-type')?.value || 'custom_compatible',
        base_url: $('provider-base-url')?.value.trim() || '',
        model_id: $('model-id')?.value.trim() || '',
        api_key: key,
        enabled: true
      });
      if ($('provider-api-key')) $('provider-api-key').value = '';
    });
    $('provider-network-toggle')?.addEventListener('click', () => {
      const enabled = $('provider-network-toggle').dataset.enabled !== 'true';
      if (enabled && !window.confirm('Cho phép AI-DG gửi request thật tới provider cho đến khi tắt?')) return;
      request(enabled ? 'provider_network_enable' : 'provider_network_disable');
    });
    container.dataset.actionsReady = '1';
  }

  function ruby(name, payload) {
    if (window.sketchup && typeof window.sketchup[name] === 'function') {
      window.sketchup[name](JSON.stringify(payload || {}));
      return true;
    }
    return false;
  }

  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[c]));
  }

  function text(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value;
    return JSON.stringify(value, null, 2);
  }

  function metric(label, value, kind) {
    return '<div class="card metric-card"><div class="label">' + esc(label) +
      '</div><div class="value ' + (kind || '') + '">' + esc(value) + '</div></div>';
  }

  function statusClass(status) {
    const value = String(status || '').toUpperCase();
    if (value === 'SUCCESS' || value === 'ONLINE' || value === 'CONNECTED' || value === 'READY') return 'status-good';
    if (value === 'ERROR' || value === 'TIMEOUT' || value === 'BLOCKED' || value === 'CANCELLED' || value === 'DISCONNECTED') return 'status-bad';
    if (value === 'NOT_VERIFIED' || value === 'NOT_CONFIGURED' || value === 'UNCONFIGURED' || value === 'TESTING' || value === 'NOT_RUN' || value === 'OFFLINE') return 'status-warn';
    if (value === 'AUTH_ERROR' || value === 'RATE_LIMITED' || value === 'NO_CREDIT' || value === 'MODEL_ERROR') return 'status-bad';
    if (value === 'RUNNING' || value === 'WAITING') return 'status-warn';
    return 'status-muted';
  }

  function explainError(value) {
    const raw = String(value ?? '');
    const code = (raw.match(/[A-Z][A-Z0-9_]{3,}/g) || []).find(item => [
      'MODEL_REQUIRED', 'API_KEY_REQUIRED', '9ROUTER_CREDENTIAL_NOT_FOUND',
      '9ROUTER_ENDPOINT_NOT_FOUND', 'PROVIDER_HELPER_INVALID_RESPONSE',
      'PROVIDER_HELPER_PROCESS_FAILED', 'PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE',
      'CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE', 'CODEX_CLI_NOT_FOUND',
      'CODEX_MCP_NOT_CONFIGURED'
    ].includes(item));
    const messages = {
      MODEL_REQUIRED: 'Chưa chọn Canonical model ID. Mở Chọn model, chọn một model, chuyển MANUAL và bấm Lưu model.',
      API_KEY_REQUIRED: 'Chưa thấy API key trong Windows Credential Manager. Vào Cài đặt → 9Router và lưu key mới.',
      '9ROUTER_CREDENTIAL_NOT_FOUND': 'Chưa thấy credential 9Router. Vào Cài đặt → 9Router và lưu key mới.',
      '9ROUTER_ENDPOINT_NOT_FOUND': 'Thiếu endpoint 9Router. Kiểm tra Base URL rồi bấm Lưu provider.',
      PROVIDER_HELPER_INVALID_RESPONSE: 'Helper provider không trả về JSON hợp lệ. Kiểm tra Python 3.12/runtime rồi dùng Diagnostics; không có fallback trả lời giả.',
      PROVIDER_HELPER_PROCESS_FAILED: 'Không chạy được provider helper. Kiểm tra Python 3.12 và quyền chạy process trong Diagnostics.',
      PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE: 'Provider đang bị chặn an toàn. Bấm Cho phép gọi provider trước khi Test hoặc chat thật.',
      CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE: 'Codex CLI đang bị chặn an toàn. Bấm Cho phép Codex CLI trước khi chat thật.',
      CODEX_CLI_NOT_FOUND: 'Không tìm thấy Codex CLI. Kiểm tra cài đặt codex.cmd rồi làm mới backend.',
      CODEX_MCP_NOT_CONFIGURED: 'Codex chưa được nối với AI-DG MCP. Kiểm tra wrapper trong workspace rồi thử lại.'
    };
    return code && messages[code] ? messages[code] + ' [' + code + ']' : raw;
  }

  function renderChatReadiness() {
    const target = $('chat-readiness');
    if (!target) return;
    const provider = state.providerAudit || {};
    const modelData = state.modelStatus || {};
    const providerStatus = String(provider.status || state.runtime?.provider_status || 'UNCONFIGURED').toUpperCase();
    const providerName = String(provider.provider || state.runtime?.provider || '—').trim() || '—';
    const backendData = state.agentBackend || {};
    const backend = String(backendData.backend || '9router').toLowerCase();
    const hasCredential = provider.credential_present === true;
    const hasEndpoint = Array.isArray(provider.endpoint_candidates) && provider.endpoint_candidates.length > 0;
    const model = String(modelData.configured_model || state.runtime?.model_ai || '').trim();
    const hasModel = Boolean(model && model !== 'AUTO');
    const modelsSource = String(modelData.models_source || '').toUpperCase();
    if (backend === 'codex_cli') {
      if ($('chat-provider-chip')) $('chat-provider-chip').textContent = 'BACKEND: Codex CLI';
      if ($('chat-model-chip')) $('chat-model-chip').textContent = 'MODEL: Codex default';
      if (backendData.codex_cli_available === false) {
        target.textContent = 'Chưa sẵn sàng: không tìm thấy Codex CLI trên máy.';
        target.className = 'chat-readiness status-bad';
        return;
      }
      if (backendData.network_permission !== 'ENABLED_FOR_EXPLICIT_ACTIONS') {
        target.textContent = 'Codex CLI đã tìm thấy; bấm Cho phép gọi provider để cho phép một lượt chat thật.';
        target.className = 'chat-readiness status-warn';
        return;
      }
      target.textContent = 'Codex CLI sẵn sàng · sandbox read-only · mỗi lượt chạy ephemeral.';
      target.className = 'chat-readiness status-good';
      return;
    }
    if ($('chat-provider-chip')) $('chat-provider-chip').textContent = 'PROVIDER: ' + providerName;
    if ($('chat-model-chip')) $('chat-model-chip').textContent = 'MODEL: ' + (hasModel ? model : 'AUTO');

    if (!hasCredential) {
      target.textContent = 'Chưa sẵn sàng: chưa thấy API key trong Windows Credential Manager. Mở Cài đặt → 9Router / Provider và lưu key.';
      target.className = 'chat-readiness status-bad';
      return;
    }
    if (!hasEndpoint) {
      target.textContent = 'Chưa sẵn sàng: thiếu Base URL provider. Nhập Base URL OpenAI-compatible rồi bấm Lưu provider.';
      target.className = 'chat-readiness status-bad';
      return;
    }
    if (!hasModel) {
      target.textContent = 'Đã nhận key và endpoint; chưa chọn model. Vào Cài đặt → Sync Models hoặc nhập Canonical model ID rồi Lưu model.';
      target.className = 'chat-readiness status-warn';
      return;
    }
    if (providerStatus !== 'CONNECTED') {
      target.textContent = 'Đã chọn model nhưng provider chưa được xác minh. Bấm Test (opt-in) trước khi chat thật · model: ' + model;
      target.className = 'chat-readiness status-warn';
      return;
    }
    target.textContent = 'Sẵn sàng gửi chat thật · ' + providerStatus + ' · model: ' + model;
    target.className = 'chat-readiness ' + statusClass(providerStatus);
  }

  function renderRuntime(data) {
    state.runtime = data || {};
    applyDeveloperMode(data);
    const health = data.health || {};
    $('runtime-cards').innerHTML = [
      metric('SketchUp PID', data.sketchup_pid || '-', 'good'),
      metric('SketchUp version', data.sketchup_version || '-', 'good'),
      metric('Model title', data.model_title || '(Untitled)'),
      metric('Bridge', health.bridge || 'UNKNOWN', statusClass(health.bridge)),
      metric('MCP', health.mcp || 'UNKNOWN', statusClass(health.mcp)),
      metric('Agent', health.agent || 'UNKNOWN', statusClass(health.agent)),
      metric('Provider', data.provider || 'Not configured'),
      metric('Model AI', data.model_ai || 'Not configured'),
      metric('9Router', health.router || 'NOT VERIFIED', statusClass(health.router)),
      metric('Active tool', data.active_tool || 'IDLE'),
      metric('Latency', data.last_latency_ms === null || data.last_latency_ms === undefined ? '-' : data.last_latency_ms + ' ms'),
      metric('LLM request', data.llm_request_state || 'IDLE'),
      metric('Runtime', data.uptime_seconds ? data.uptime_seconds + 's' : '-'),
      metric('Tokens', data.token_count === null || data.token_count === undefined ? '-' : data.token_count),
      metric('Cost', data.cost === null || data.cost === undefined ? '-' : data.cost)
    ].join('');

    const mode = data.access_mode || 'read_only';
    $('mode-badge').textContent = mode.toUpperCase().replace('_', ' ');
    $('mode-badge').style.color = mode === 'write_enabled' ? 'var(--gold)' : 'var(--cyan)';
    $('mode-toggle').textContent = mode === 'write_enabled' ? 'Tắt ghi model' : 'Bật ghi model';
    $('footer-status').textContent = (health.bridge || 'UNKNOWN') + ' · ' + (health.mcp || 'UNKNOWN');
    $('task-summary').innerHTML = data.current_task ? esc(data.current_task) : '<span class="empty">Chưa có task agent.</span>';
    $('queue-summary').innerHTML = [
      ['Command queue', data.command_queue ?? 0],
      ['Result queue', data.result_queue ?? 0],
      ['Trace events', (data.trace || []).length],
      ['Last latency', data.last_latency_ms === null || data.last_latency_ms === undefined ? '-' : data.last_latency_ms + ' ms']
    ].map(x => '<div class="health-row"><span>' + esc(x[0]) + '</span><strong>' + esc(x[1]) + '</strong></div>').join('');
    $('runtime-health').innerHTML = [
      ['Bridge', health.bridge || 'UNKNOWN'], ['MCP', health.mcp || 'UNKNOWN'],
      ['Agent', health.agent || 'UNKNOWN'], ['Provider', health.provider || 'UNCONFIGURED'], ['Model AI', data.model_ai || 'Not configured'],
      ['9Router', health.router || 'OFFLINE'], ['Mode', mode],
      ['Model path', data.model_path || '(unsaved)'], ['Active skill', data.active_skill || 'IDLE'],
      ['Active plugin', data.active_plugin || 'IDLE'], ['Tokens', data.token_count ?? '-'], ['Cost', data.cost ?? '-'],
      ['Errors', (data.errors || []).length],
      ['Warnings', (data.warnings || []).length]
    ].map(x => '<div class="health-row"><span>' + esc(x[0]) + '</span><strong>' + esc(x[1]) + '</strong></div>').join('');

    state.trace = data.trace || [];
    renderFlow();
    renderSequence();
    renderToolCalls();
    renderAgentSteps();
    renderErrors();
    $('developer-trace').textContent = text({ runtime: data, trace: state.trace });
    $('runtime-source').textContent = text({
      source: data.bridge_source || '(not reported)',
      sha256: data.bridge_source_sha256 || '(not reported)',
      reload_generation: data.reload_generation ?? 0
    });
    const manager = data.model_manager || {};
    renderModelCatalog(manager.available_models || [], manager.models_source);
    if ($('provider-name')) $('provider-name').textContent = manager.provider || data.provider || 'Chưa cấu hình';
    if ($('provider-status')) $('provider-status').textContent = manager.provider_status || data.provider_status || 'NOT_QUERIED';
    if ($('provider-endpoint')) $('provider-endpoint').textContent = manager.endpoint_count ? manager.endpoint_count + ' candidate(s), redacted' : '********';
    if ($('model-status')) $('model-status').textContent = manager.network_test || 'NOT_QUERIED';
    if ($('model-id') && document.activeElement !== $('model-id')) $('model-id').value = manager.model && manager.model !== 'AUTO' ? manager.model : '';
    if ($('model-mode')) $('model-mode').value = manager.mode || 'AUTO';
    if ($('settings-session')) $('settings-session').textContent = data.session_id || 'chưa có';
    if ($('settings-mcp')) $('settings-mcp').textContent = health.mcp || 'UNKNOWN';
    if ($('settings-developer')) $('settings-developer').textContent = data.developer_mode ? 'ON' : 'OFF';
    if ($('settings-agent')) $('settings-agent').textContent = health.agent || 'UNKNOWN';
    renderChatReadiness();
  }

  function renderPipeline(data) {
    const pipeline = data?.data || data || {};
    state.pipeline = pipeline;
    if ($('pipeline-source-cards')) {
      $('pipeline-source-cards').innerHTML = [
        metric('Run', pipeline.run_id || '-', 'good'),
        metric('Gate', pipeline.gate_status || pipeline.status || 'NOT_RUN', statusClass(pipeline.gate_status || pipeline.status)),
        metric('Nguồn', pipeline.package_count ?? '-', ''),
        metric('Bản vẽ', pipeline.drawing_count ?? '-', ''),
        metric('Dimension facts', pipeline.dimension_count ?? '-', ''),
        metric('Material facts', pipeline.material_count ?? '-', '')
      ].join('');
    }
    if ($('pipeline-source-data')) $('pipeline-source-data').textContent = text(pipeline);
    const reviewItems = Array.isArray(pipeline.review_items) ? pipeline.review_items : [];
    if ($('pipeline-review-list')) {
      $('pipeline-review-list').innerHTML = reviewItems.length
        ? reviewItems.map(item => '<div class="trace-row"><strong class="' + statusClass(item.severity) + '">' + esc(item.severity || 'REVIEW') + '</strong><span>' + esc(item.issue || item.code || '-') + '</span><small>' + esc(item.status || 'OPEN') + ' · ' + esc(item.impact || '') + '</small></div>').join('')
        : '<div class="empty">Không có review item trong run gần nhất.</div>';
    }
    const operations = Array.isArray(pipeline.build_operations) ? pipeline.build_operations : [];
    const blockedItems = Array.isArray(pipeline.blocked_items) ? pipeline.blocked_items : [];
    if ($('pipeline-build-cards')) {
      $('pipeline-build-cards').innerHTML = [
        metric('Gate', pipeline.gate_status || 'NOT_RUN', statusClass(pipeline.gate_status)),
        metric('Operations', operations.length, operations.length ? 'good' : ''),
        metric('Blocked', blockedItems.length, blockedItems.length ? 'status-bad' : 'good')
      ].join('');
    }
    if ($('pipeline-build-list')) {
      const rows = operations.map(operation => '<div class="trace-row"><strong>' + esc(operation.op || '-') + '</strong><span>' + esc(operation.item_code || '-') + '</span><small>' + esc(operation.execution_tool || '') + '</small></div>');
      blockedItems.forEach(item => rows.push('<div class="trace-row"><strong class="status-bad">BLOCKED</strong><span>' + esc(item.item_code || '-') + '</span><small>' + esc(item.reason || '') + '</small></div>'));
      $('pipeline-build-list').innerHTML = rows.length ? rows.join('') : '<div class="empty">Chưa có semantic build operation.</div>';
    }
  }

  function latestStatus(predicate, fallback) {
    const row = state.trace.slice().reverse().find(predicate);
    return row ? (row.status || fallback) : fallback;
  }

  function renderFlow() {
    const health = state.runtime?.health || {};
    const toolStatus = latestStatus(row => row.event === 'tool_finished' || row.event === 'tool_started', 'IDLE');
    const agentStatus = latestStatus(row => row.event === 'agent_finished' || row.event === 'agent_started', 'IDLE');
    const nodes = [
      ['USER', agentStatus === 'RUNNING' ? 'WAITING' : 'IDLE'],
      ['AI-DG UI', 'CONNECTED'], ['AGENT', agentStatus],
      ['9ROUTER', health.router || 'NOT_VERIFIED'],
      ['MODEL', health.provider === 'NOT_CONFIGURED' ? 'BLOCKED' : 'IDLE'],
      ['MCP', health.mcp || 'UNKNOWN'], ['TOOL', toolStatus],
      ['RUBY BRIDGE', health.bridge || 'UNKNOWN'], ['SKETCHUP API', toolStatus],
      ['MODEL', toolStatus === 'SUCCESS' ? 'SUCCESS' : 'IDLE'],
      ['RESULT', toolStatus === 'SUCCESS' ? 'SUCCESS' : 'WAITING']
    ];
    $('flow-graph').innerHTML = nodes.map((node, index) =>
      '<button class="flow-node" data-flow-node="' + index + '"><strong>' + esc(node[0]) +
      '</strong><span class="state ' + statusClass(node[1]) + '">' + esc(node[1]) +
      '</span></button>' + (index < nodes.length - 1 ? '<span class="flow-arrow">→</span>' : '')
    ).join('');
    document.querySelectorAll('[data-flow-node]').forEach(button => button.addEventListener('click', () => {
      renderFlowDetails(button.dataset.flowNode);
    }));
    renderFlowDetails(null);
  }

  function traceRow(row) {
    const detail = [row.event || row.stage || 'event', row.tool ? 'tool=' + row.tool : '', row.skill ? 'skill=' + row.skill : '', row.request_id ? 'request=' + row.request_id : '', row.latency_ms !== undefined ? 'latency=' + row.latency_ms + 'ms' : ''].filter(Boolean).join(' · ');
    const metadata = [row.session_id ? 'session=' + row.session_id : '', row.bytes_in !== undefined ? 'in=' + row.bytes_in + 'B' : '', row.bytes_out !== undefined ? 'out=' + row.bytes_out + 'B' : '', row.token_count !== undefined ? 'tokens=' + row.token_count : '', row.retries !== undefined ? 'retry=' + row.retries : '', row.error ? 'error=' + row.error : ''].filter(Boolean).join(' · ');
    const index = state.trace.indexOf(row);
    return '<button class="trace-row" data-trace-index="' + index + '"><span><strong>' + esc(detail) + '</strong><small>' + esc(metadata) + '</small></span><strong class="' + statusClass(row.status) + '">' + esc(row.status || 'SUCCESS') + '</strong><small>' + esc(row.timestamp || '') + '</small></button>';
  }

  function renderTraceList(rows) {
    const html = rows.length ? rows.map(traceRow).join('') : '<div class="empty">Chưa có event.</div>';
    return html;
  }

  function bindTraceRows() {
    document.querySelectorAll('[data-trace-index]').forEach(button => button.addEventListener('click', () => {
      const row = state.trace[Number(button.dataset.traceIndex)];
      if ($('trace-inspector')) $('trace-inspector').textContent = text(row || {});
    }));
  }

  function renderFlowDetails(nodeIndex) {
    const labels = ['USER', 'AI-DG UI', 'AGENT', '9ROUTER', 'MODEL', 'MCP', 'TOOL', 'RUBY BRIDGE', 'SKETCHUP API', 'MODEL', 'RESULT'];
    const label = nodeIndex === null || nodeIndex === undefined ? null : labels[Number(nodeIndex)];
    const rows = label === 'TOOL' || label === 'SKETCHUP API'
      ? state.trace.filter(row => String(row.event || '').startsWith('tool_')).slice(-20).reverse()
      : label === 'AGENT'
        ? state.trace.filter(row => /agent|skill|provider/i.test(String(row.event || ''))).slice(-20).reverse()
        : state.trace.slice(-20).reverse();
    $('flow-details').innerHTML = renderTraceList(rows);
    bindTraceRows();
  }

  function renderSequence() {
    const rows = state.trace.slice(-50).reverse();
    $('sequence-list').innerHTML = renderTraceList(rows);
    bindTraceRows();
  }

  function renderToolCalls() {
    const rows = state.trace.filter(row => row.event === 'tool_started' || row.event === 'tool_finished').slice(-50).reverse();
    $('tool-calls-list').innerHTML = renderTraceList(rows);
    bindTraceRows();
  }

  function renderAgentSteps() {
    const rows = state.trace.filter(row => /agent|skill|provider|model/i.test(String(row.event || row.stage || ''))).slice(-50).reverse();
    $('agent-steps-list').innerHTML = renderTraceList(rows);
    bindTraceRows();
  }

  function renderErrors() {
    const rows = state.trace.filter(row => ['ERROR', 'TIMEOUT', 'BLOCKED'].includes(String(row.status || '').toUpperCase())).slice(-50).reverse();
    $('errors-list').innerHTML = renderTraceList(rows);
    bindTraceRows();
  }

  function renderTools(data) {
    const rows = Array.isArray(data) ? data : (data?.items || []);
    const source = rows.length ? rows : fallbackTools.map(t => ({ id: t[0], permission: t[1], risk: t[2], status: 'REGISTERED' }));
    state.bridgeTools = source;
    if ($('settings-tools')) $('settings-tools').textContent = source.length;
    let html = '<div class="tool-row head"><span>Enabled</span><span>Tool</span><span>Permission</span><span>Risk</span><span>Status</span><span>Last Run</span><span>Duration</span></div>';
    html += source.map(t => '<div class="tool-row"><span class="' + (t.enabled === false ? 'status-muted' : 'status-good') + '">' + (t.enabled === false ? 'NO' : 'YES') + '</span><span>' + esc(t.id) + '</span><span>' + esc(t.permission || '-') +
      '</span><span>' + esc(t.risk || '-') + '</span><span class="' + statusClass(t.status) + '">' + esc(t.status || 'REGISTERED') +
      '</span><span>' + esc(t.last_run || '-') + '</span><span>' + esc(t.duration_ms === null || t.duration_ms === undefined ? '-' : t.duration_ms + ' ms') + '</span></div>').join('');
    $('tool-list').innerHTML = html;
  }

  function renderSkills(data) {
    const rows = Array.isArray(data) ? data : (data?.items || []);
    state.skills = rows;
    if ($('settings-skills')) $('settings-skills').textContent = rows.length;
    $('skill-list').innerHTML = rows.length ? rows.map(s => '<div class="registry-row"><strong>' + esc(s.name || s.id) + '</strong><span>' + esc(s.description || '') + '</span><small>' + esc(s.status || 'AVAILABLE') + ' · lazy <button class="secondary registry-action" data-skill-load="' + esc(s.id) + '">Load</button></small></div>').join('') : '<div class="empty">Chưa phát hiện SKILL.md.</div>';
    document.querySelectorAll('[data-skill-load]').forEach(button => button.addEventListener('click', () => request('load_skill', { skill_id: button.dataset.skillLoad, max_chars: 6000 })));
  }

  function renderPlugins(data) {
    const rows = Array.isArray(data) ? data : (data?.items || []);
    state.plugins = rows;
    if ($('settings-plugins')) $('settings-plugins').textContent = rows.length;
    $('plugin-list').innerHTML = rows.length ? rows.map(p => {
      const enabled = String(p.status || '').toUpperCase() === 'ENABLED';
      const core = p.id === 'ai-dg-core';
      const actions = core ? '' : '<button class="secondary registry-action" data-plugin-toggle="' + esc(p.id) + '" data-enabled="' + (!enabled) + '">' + (enabled ? 'Disable' : 'Enable') + '</button><button class="secondary registry-action" data-plugin-reload="' + esc(p.id) + '">Reload</button>';
      return '<div class="registry-row"><strong>' + esc(p.name || p.id) + '</strong><span>' + esc(p.description || '') + '</span><small>' + esc(p.status || 'DISABLED') + ' · ' + esc((p.permissions || []).join(', ') || 'no permissions') + ' ' + actions + '</small></div>';
    }).join('') : '<div class="empty">Chưa có plugin manifest.</div>';
    document.querySelectorAll('[data-plugin-toggle]').forEach(button => button.addEventListener('click', () => {
      const enabled = button.dataset.enabled === 'true';
      if (!window.confirm((enabled ? 'Bật' : 'Tắt') + ' plugin ' + button.dataset.pluginToggle + '?')) return;
      request('plugin_set_enabled', { plugin_id: button.dataset.pluginToggle, enabled: enabled });
    }));
    document.querySelectorAll('[data-plugin-reload]').forEach(button => button.addEventListener('click', () => request('plugin_reload', { plugin_id: button.dataset.pluginReload })));
  }

  function setAgentState(value) {
    const normalized = String(value || 'IDLE').toUpperCase();
    const busy = normalized === 'RUNNING' || normalized === 'WAITING';
    const paused = normalized === 'PAUSED';
    if ($('agent-state')) {
      $('agent-state').textContent = normalized;
      $('agent-state').className = statusClass(normalized);
    }
    if ($('chat-send')) {
      $('chat-send').disabled = busy || paused;
      $('chat-send').textContent = busy ? 'Đang xử lý…' : 'Gửi';
      $('chat-send').title = paused ? 'Agent đang tạm dừng; bấm Tiếp tục trước khi gửi.' : '';
    }
    if ($('agent-pause')) $('agent-pause').disabled = !busy;
    if ($('agent-resume')) $('agent-resume').disabled = !paused;
    if ($('agent-cancel')) $('agent-cancel').disabled = !(busy || paused);
  }

  function renderProviderAudit(data) {
    if (!data) return;
    state.providerAudit = data;
    if ($('provider-name')) $('provider-name').textContent = data.provider || '9Router';
    if ($('provider-name-input') && data.provider) $('provider-name-input').value = data.provider;
    if ($('provider-type') && data.provider_type) $('provider-type').value = data.provider_type;
    const status = data.status || 'NOT_QUERIED';
    if ($('provider-status')) $('provider-status').textContent = status;
    if ($('provider-endpoint')) $('provider-endpoint').textContent = data.endpoint_candidates?.length ? data.endpoint_candidates.join(', ') : '********';
    if ($('provider-base-url') && data.endpoint_candidates?.length && document.activeElement !== $('provider-base-url')) $('provider-base-url').value = data.endpoint_candidates[0];
    if ($('provider-network-status')) $('provider-network-status').textContent = data.network_permission || 'REQUIRES_EXPLICIT_ENABLE';
    if ($('provider-network-toggle')) {
      const enabled = data.network_permission === 'ENABLED_FOR_EXPLICIT_ACTIONS';
      $('provider-network-toggle').dataset.enabled = enabled ? 'true' : 'false';
      $('provider-network-toggle').textContent = enabled ? 'Tắt quyền gọi provider' : 'Cho phép gọi provider';
    }
    const providerCard = $('provider-status')?.closest('.card');
    const last = data.last_test || {};
    if (providerCard && !$('provider-last-test')) {
      const row = document.createElement('div');
      row.className = 'setting-row';
      row.innerHTML = '<span>Last Test</span><strong id="provider-last-test"></strong>';
      providerCard.querySelector('.head-actions')?.before(row);
    }
    if ($('provider-last-test')) {
      $('provider-last-test').textContent = last.status
        ? [last.status, last.latency_ms !== undefined ? last.latency_ms + ' ms' : '', last.request_count !== undefined ? 'req=' + last.request_count : ''].filter(Boolean).join(' · ')
        : (data.network_test || 'NOT_RUN');
    }
    setProviderRecovery(/ERROR|UNCONFIGURED|AUTH_ERROR|RATE_LIMITED|NO_CREDIT|OFFLINE|MODEL_ERROR/i.test(status));
    renderChatReadiness();
  }

  function renderAgentBackend(data) {
    if (!data) return;
    state.agentBackend = data;
    if ($('agent-backend')) $('agent-backend').value = data.backend || '9router';
    if ($('agent-backend-status')) {
      $('agent-backend-status').textContent = data.backend === 'codex_cli'
        ? (data.codex_cli_available === false ? 'CODEX CLI NOT FOUND' : 'CODEX CLI AVAILABLE')
        : '9ROUTER';
    }
    if ($('agent-backend-network-toggle')) {
      const enabled = data.network_permission === 'ENABLED_FOR_EXPLICIT_ACTIONS';
      $('agent-backend-network-toggle').dataset.enabled = enabled ? 'true' : 'false';
      $('agent-backend-network-toggle').textContent = data.backend === 'codex_cli'
        ? (enabled ? 'Tắt quyền Codex CLI' : 'Cho phép Codex CLI')
        : 'Chọn Codex để bật quyền riêng';
      $('agent-backend-network-toggle').disabled = data.backend !== 'codex_cli';
    }
    renderChatReadiness();
  }

  function setProviderRecovery(visible) {
    const actions = $('provider-actions');
    if (actions) actions.hidden = !visible;
  }

  function renderModelStatus(data) {
    if (!data) return;
    state.modelStatus = data;
    if ($('model-status')) $('model-status').textContent = data.network_test || data.status || 'NOT_QUERIED';
    if ($('model-id') && document.activeElement !== $('model-id')) $('model-id').value = data.model && data.model !== 'AUTO' ? data.model : (data.configured_model || '');
    if ($('model-mode')) $('model-mode').value = data.mode || 'AUTO';
    renderModelCatalog(data.available_models || [], data.models_source);
    renderChatReadiness();
  }

  function renderModelCatalog(models, source) {
    const input = $('model-id');
    if (!input) return;
    let datalist = $('model-options');
    if (!datalist) {
      datalist = document.createElement('datalist');
      datalist.id = 'model-options';
      input.setAttribute('list', datalist.id);
      input.insertAdjacentElement('afterend', datalist);
    }
    const rows = Array.isArray(models) ? models.slice(0, 200) : [];
    datalist.innerHTML = rows.map(model => '<option value="' + esc(model.id || '') + '">' + esc(model.name || model.id || '') + '</option>').join('');
    let summary = $('model-catalog');
    if (!summary) {
      summary = document.createElement('div');
      summary.id = 'model-catalog';
      summary.className = 'empty';
      input.parentElement?.parentElement?.appendChild(summary);
    }
    while (summary.firstChild) summary.removeChild(summary.firstChild);
    const label = document.createElement('div');
    if (!rows.length) label.textContent = 'Chưa sync model.';
    else if (String(source || '').toUpperCase() === 'LOCAL_9ROUTER_CACHE') label.textContent = 'Có ' + rows.length + ' model từ cache 9Router cục bộ; chưa xác minh endpoint. Chọn canonical ID rồi Lưu model.';
    else label.textContent = 'Đã sync ' + rows.length + ' model; chọn canonical ID.';
    summary.appendChild(label);

    if (!rows.length) return;
    const suggestions = document.createElement('div');
    suggestions.className = 'model-suggestions';
    rows.slice(0, 6).forEach(model => {
      const id = String(model?.id || '').trim();
      if (!id) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secondary model-suggestion';
      button.textContent = id;
      button.title = 'Điền ' + id + ' vào Model Manager; chưa tự lưu';
      button.addEventListener('click', () => {
        input.value = id;
        if ($('model-mode')) $('model-mode').value = 'MANUAL';
        input.focus();
        renderChatReadiness();
      });
      suggestions.appendChild(button);
    });
    summary.appendChild(suggestions);
  }

  function renderModel(data) {
    if (!data) return;
    $('model-summary').innerHTML = [
      metric('Model', data.title || '(Untitled)'), metric('Path', data.path || '(unsaved)'),
      metric('Entities', data.entities ?? '-'), metric('Bounds mm', data.bounds_mm ? data.bounds_mm.join(' × ') : '-')
    ].join('');
  }

  function renderCodeView(data) {
    if (!data) return;
    if ($('developer-request')) $('developer-request').textContent = data.last_mcp_request_json || '{}';
    if ($('developer-response')) $('developer-response').textContent = data.last_mcp_response_json || '{}';
    if ($('developer-context')) $('developer-context').textContent = text({ active_skill: data.active_skill, active_plugin: data.active_plugin, errors: data.runtime_errors || [] });
    const files = Array.isArray(data.source_files) ? data.source_files : [];
    if ($('developer-code-files')) {
      $('developer-code-files').innerHTML = files.length ? files.map((file, index) => '<article class="developer-code"><div class="developer-code-head"><strong>' + esc(file.label || file.path) + '</strong><span>' + esc(file.path || '') + ':' + esc(file.start_line || 1) + '</span><div><button class="secondary developer-open" data-code-index="' + index + '">Open File</button><button class="secondary developer-copy" data-code-index="' + index + '">Copy</button></div></div><pre class="json-box">' + esc(file.excerpt || '(source unavailable)') + '</pre></article>').join('') : '<div class="empty">Chưa có source.</div>';
      document.querySelectorAll('.developer-code-head div').forEach((container, index) => {
        if (container.querySelector('.developer-view')) return;
        const view = document.createElement('button');
        view.className = 'secondary developer-view';
        view.dataset.codeIndex = index;
        view.textContent = 'View Source';
        container.appendChild(view);
      });
      document.querySelectorAll('[data-code-index]').forEach(button => button.addEventListener('click', () => {
        const file = files[Number(button.dataset.codeIndex)];
        if (!file) return;
        if (button.classList.contains('developer-open')) request('open_file', { path: file.path });
        if (button.classList.contains('developer-copy')) navigator.clipboard?.writeText(file.excerpt || '');
        if (button.classList.contains('developer-view')) {
          const pre = button.closest('.developer-code')?.querySelector('pre');
          const expanded = pre?.classList.toggle('developer-source-expanded');
          button.textContent = expanded ? 'Thu gọn source' : 'View Source';
        }
      }));
    }
  }

  function renderLogs(data) {
    const files = data && data.files ? data.files : {};
    const entries = Object.entries(files);
    $('log-list').innerHTML = entries.length ? entries.map(([name, file]) => '<article class="card log-card"><div class="card-head"><h2>' + esc(name) + '</h2><small>' + esc(file.path || '') + '</small></div><pre class="json-box">' + esc((file.lines || []).join('')) + '</pre></article>').join('') : '<div class="empty">Chưa có log.</div>';
  }

  function renderCollection(id, data) {
    $(id).textContent = text(data);
  }

  function updateSelection(data) {
    renderCollection('selection-data', data);
    const item = data && data.items && data.items.length === 1 ? data.items[0] : null;
    state.selectedEntityId = item && item.persistent_id ? item.persistent_id : null;
    $('inspect-selection').disabled = !state.selectedEntityId;
  }

  function request(action, data) {
    ruby('ai_dg_action', { action: action, data: data || {} });
  }

  function receive(message) {
    const data = message && message.data ? message.data : message;
    const responseData = message && message.error ? { status: 'error', error: message.error } : data;
    if (data && data.health) { renderRuntime(data); return; }
    if (message.action === 'pipeline_status') { renderPipeline(data?.data || data); return; }
    if (message.action === 'list_tools') { renderTools(data); return; }
    if (message.action === 'list_skills') { renderSkills(data); return; }
    if (message.action === 'list_plugins') { renderPlugins(data); return; }
    if (message.action === 'load_skill') { $('skill-details').textContent = text(responseData); return; }
    if (message.action === 'plugin_set_enabled' || message.action === 'plugin_reload') { request('list_plugins'); return; }
    if (message.action === 'get_hierarchy') { renderCollection('hierarchy-data', responseData); return; }
    if (message.action === 'get_entity') { renderCollection('entity-data', responseData); return; }
    if (message.action === 'list_components') { renderCollection('components-data', responseData); return; }
    if (message.action === 'list_materials') { renderCollection('materials-data', responseData); return; }
    if (message.action === 'list_tags') { renderCollection('tags-data', responseData); return; }
    if (message.action === 'list_scenes') { renderCollection('scenes-data', responseData); return; }
    if (message.action === 'reload_runtime') {
      $('reload-result').textContent = message.error || text(message);
      request('get_runtime_state');
      return;
    }
    if (data && data.title !== undefined) { renderModel(data); return; }
    if (message.action === 'get_selection') { updateSelection(responseData); return; }
    if (message.action === 'get_camera') { $('camera-data').textContent = text(data); return; }
    if (message.action === 'chat_started') {
      setAgentState(data?.agent_state || 'RUNNING');
      appendChat('system', 'Agent đang xử lý request ' + (data?.request_id || '') + ' · backend: ' + (data?.backend || '9router') + ' · tối đa 2 bước / 1 tool.');
      return;
    }
    if (message.action === 'chat') {
      const chat = data || message || {};
      appendChat('agent', explainError(chat.answer || chat.result || chat.error || chat));
      const trace = [
        chat.mcp_server ? 'mcp=' + chat.mcp_server : '',
        chat.skill ? 'skill=' + chat.skill : '',
        chat.tool ? 'tool=' + chat.tool : '',
        chat.tool_calls !== undefined ? 'tool_calls=' + chat.tool_calls : '',
        chat.request_count !== undefined ? 'provider_req=' + chat.request_count : ''
      ].filter(Boolean).join(' · ');
      if (trace) appendChat('system', 'Trace: ' + trace);
      const blocked = chat.agent_state === 'BLOCKED' || chat.status === 'blocked' || message.status === 'blocked';
      setAgentState(chat.agent_state || (blocked ? 'BLOCKED' : 'IDLE'));
      return;
    }
    if (message.action === 'agent_cancel' || message.action === 'agent_pause' || message.action === 'agent_resume' || message.action === 'agent_status') {
      setAgentState(data?.agent_state || data?.status || 'IDLE');
      return;
    }
    if (message.action === 'provider_audit') { renderProviderAudit(data?.data || data); return; }
    if (message.action === 'agent_backend_status' || message.action === 'agent_backend_select' || message.action === 'codex_network_enable' || message.action === 'codex_network_disable') { renderAgentBackend(data?.data || data); return; }
    if (message.action === 'provider_network_enable' || message.action === 'provider_network_disable') {
      const result = data?.data || data || {};
      const enabled = result.enabled === true || result.network_permission === 'ENABLED_FOR_EXPLICIT_ACTIONS';
      if ($('provider-network-status')) $('provider-network-status').textContent = result.network_permission || (enabled ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE');
      if ($('provider-network-toggle')) {
        $('provider-network-toggle').dataset.enabled = enabled ? 'true' : 'false';
        $('provider-network-toggle').textContent = enabled ? 'Tắt quyền gọi provider' : 'Cho phép gọi provider';
      }
      return;
    }
    if (message.action === 'provider_configure') {
      const result = data?.data || data || {};
      appendChat('system', result.status === 'ok' ? 'Đã lưu provider; API key nằm trong Windows Credential Manager.' : ('Không lưu được provider: ' + (result.error || 'UNKNOWN_ERROR') + (result.detail ? ' · ' + result.detail : '')));
      request('provider_audit');
      request('model_status');
      return;
    }
    if (message.action === 'provider_test' || message.action === 'provider_test_started' || message.action === 'provider_sync' || message.action === 'provider_sync_started' || message.action === 'provider_disconnect') {
      const result = data?.data || data || {};
      if ($('provider-status')) $('provider-status').textContent = result.error || result.status || 'NOT_RUN';
      if (message.action.endsWith('_started')) appendChat('system', 'Đang chạy ' + message.action.replace('_started', '') + ' bằng provider thật…');
       else appendChat('system', result.status === 'ok' ? 'Provider action hoàn tất.' : ('Provider action: ' + explainError(result.error || result.status || 'BLOCKED')));
      setProviderRecovery(message.action === 'provider_disconnect' || Boolean(result.error));
      if (message.action === 'provider_test' || message.action === 'provider_sync' || message.action === 'provider_disconnect') request('provider_audit');
      return;
    }
    if (message.action === 'model_status' || message.action === 'model_select') { renderModelStatus(data?.data || data); return; }
    if (message.action === 'plugin_diagnostics') { if ($('plugin-diagnostics-data')) $('plugin-diagnostics-data').textContent = text(data?.data || data); return; }
    if (message.action === 'get_code_view') { renderCodeView(data?.data || data); return; }
    if (message.action === 'get_logs') { renderLogs(data?.data || data); return; }
    if (message.error) {
      const error = String(message.error);
      if (/BRIDGE_|MCP_|READ_TIMEOUT|DISCONNECT|SketchUp bridge/i.test(error)) {
        if ($('footer-status')) $('footer-status').textContent = 'ONLINE · DISCONNECTED';
        if ($('settings-mcp')) $('settings-mcp').textContent = 'DISCONNECTED';
        appendChat('system', 'MCP DISCONNECTED: ' + error);
      } else if (/9ROUTER|PROVIDER/i.test(error)) {
        if ($('provider-status')) $('provider-status').textContent = 'PROVIDER_UNAVAILABLE';
        setProviderRecovery(true);
        appendChat('system', 'Provider unavailable: ' + explainError(error));
      } else {
        appendChat('agent', 'Lỗi: ' + explainError(error));
      }
    }
  }

  function renderChatMessage(kind, value, timestamp) {
    const item = document.createElement('div');
    const safeKind = ['user', 'agent', 'system'].includes(kind) ? kind : 'system';
    const bodyText = typeof value === 'string' ? value : text(value);
    item.className = 'chat-msg ' + safeKind;
    const body = document.createElement('div');
    body.className = 'chat-body';
    body.textContent = bodyText;
    const meta = document.createElement('div');
    meta.className = 'chat-meta';
    const when = timestamp ? new Date(timestamp) : new Date();
    const timeText = Number.isNaN(when.getTime()) ? '' : when.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    meta.textContent = ({ user: 'USER', agent: 'AI-DG', system: 'SYSTEM' }[safeKind] || 'SYSTEM') + (timeText ? ' · ' + timeText : '');
    item.appendChild(body);
    item.appendChild(meta);
    $('chat-history').appendChild(item);
    $('chat-history').scrollTop = $('chat-history').scrollHeight;
    return { item: item, kind: safeKind, text: bodyText };
  }

  function appendChat(kind, value) {
    const timestamp = new Date().toISOString();
    const rendered = renderChatMessage(kind, value, timestamp);
    try {
      const messages = JSON.parse(localStorage.getItem('ai-dg-chat-session') || '[]');
      messages.push({ kind: rendered.kind, text: rendered.text, timestamp: timestamp });
      localStorage.setItem('ai-dg-chat-session', JSON.stringify(messages.slice(-200)));
    } catch (_) { /* local storage may be unavailable in a restricted HtmlDialog */ }
  }

  function restoreChat() {
    try {
      const messages = JSON.parse(localStorage.getItem('ai-dg-chat-session') || '[]');
      if (messages.length) {
        const placeholder = document.querySelector('#chat-history .chat-msg.system');
        if (placeholder) placeholder.remove();
      }
      messages.forEach(message => {
        renderChatMessage(message.kind || 'system', message.text || '', message.timestamp);
      });
    } catch (_) { /* keep the initial system message */ }
  }

  function sendChat() {
    const input = $('chat-text');
    if (!input || $('chat-send')?.disabled) return;
    const message = input.value.trim();
    if (!message) return;
    appendChat('user', message);
    input.value = '';
    setAgentState('RUNNING');
    if (!ruby('ai_dg_chat', { message: message })) {
      setAgentState('ERROR');
      appendChat('system', 'MCP DISCONNECTED: không gửi được request tới SketchUp bridge.');
    }
    input.focus();
  }

  document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
    if (button.hidden) return;
    state.selectedTab = button.dataset.tab;
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    button.classList.add('active');
    $('panel-' + button.dataset.tab).classList.add('active');
    if (button.dataset.tab === 'tools') request('list_tools');
    if (button.dataset.tab === 'skills') request('list_skills');
    if (button.dataset.tab === 'plugins') request('list_plugins');
    if (button.dataset.tab === 'settings') { request('provider_audit'); request('model_status'); request('list_tools'); request('list_skills'); request('list_plugins'); }
    if (button.dataset.tab === 'model') {
      request('get_model_info'); request('get_selection'); request('get_camera');
      request('get_hierarchy', { max_depth: 3, max_items: 200 }); request('list_components');
      request('list_materials'); request('list_tags'); request('list_scenes');
    }
    if (button.dataset.tab === 'developer') request('get_code_view');
    if (button.dataset.tab === 'logs') request('get_logs', { limit: 80 });
    if (['sources', 'review', 'build'].includes(button.dataset.tab)) request('pipeline_status');
  }));

  $('refresh-runtime').addEventListener('click', () => request('get_runtime_state'));
  $('refresh-model').addEventListener('click', () => { request('get_model_info'); request('get_selection'); request('get_camera'); request('get_hierarchy', { max_depth: 3, max_items: 200 }); request('list_components'); request('list_materials'); request('list_tags'); request('list_scenes'); });
  $('inspect-selection').addEventListener('click', () => { if (state.selectedEntityId) request('get_entity', { persistent_id: state.selectedEntityId }); });
  $('refresh-skills').addEventListener('click', () => request('list_skills'));
  $('refresh-plugins').addEventListener('click', () => request('list_plugins'));
  $('plugin-diagnostics').addEventListener('click', () => request('plugin_diagnostics'));
  $('reload-runtime').addEventListener('click', () => request('reload_runtime'));
  $('developer-refresh').addEventListener('click', () => request('get_code_view'));
  $('refresh-logs').addEventListener('click', () => request('get_logs', { limit: 80 }));
  $('refresh-pipeline-sources').addEventListener('click', () => request('pipeline_status'));
  $('refresh-pipeline-review').addEventListener('click', () => request('pipeline_status'));
  $('refresh-pipeline-build').addEventListener('click', () => request('pipeline_status'));
  $('provider-audit').addEventListener('click', () => request('provider_audit'));
  $('provider-refresh').addEventListener('click', () => { request('provider_audit'); request('model_status'); });
  $('provider-retry').addEventListener('click', () => {
    appendChat('system', 'Đang kiểm tra lại provider ở chế độ an toàn; network test vẫn cần opt-in.');
    request('provider_audit');
    request('model_status');
  });
  $('provider-change-model').addEventListener('click', () => {
    $('model-id').focus();
    $('model-id').select();
  });
  $('provider-diagnostics').addEventListener('click', () => {
    request('provider_audit');
    request('model_status');
    request('plugin_diagnostics');
  });
  $('model-refresh').addEventListener('click', () => request('model_status'));
  $('model-save').addEventListener('click', () => request('model_select', { model: $('model-mode').value === 'AUTO' ? '' : $('model-id').value.trim() }));
  $('agent-pause').addEventListener('click', () => request('agent_pause'));
  $('agent-resume').addEventListener('click', () => request('agent_resume'));
  $('agent-cancel').addEventListener('click', () => request('agent_cancel'));
  $('mode-toggle').addEventListener('click', () => {
    const enabling = !(state.runtime && state.runtime.access_mode === 'write_enabled');
    if (enabling && !window.confirm('Bật WRITE ENABLED sẽ cho phép các tool ghi model. Tiếp tục?')) return;
    request('set_mode', { mode: enabling ? 'write_enabled' : 'read_only' });
  });
  $('chat-send').addEventListener('click', sendChat);
  $('chat-text').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });
  $('chat-open-settings').addEventListener('click', () => openSettingsGroup('provider'));

  window.aiDgReceive = receive;
  applyDeveloperMode({ developer_mode: false });
  initializeSettingsTabs();
  initializeChatNavigationControls();
  initializeAgentBackendControls();
  initializeProviderActions();
  setAgentState('IDLE');
  renderTools([]);
  renderSkills([]);
  renderPlugins([]);
  restoreChat();
  ruby('ai_dg_ready', {});
  request('get_runtime_state');
  request('provider_audit');
  request('model_status');
  request('agent_backend_status');
  request('pipeline_status');
}());

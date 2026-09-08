# frozen_string_literal: true

# AI-DG SketchUp Control Center.
#
# This module is intentionally a broker. It owns the HtmlDialog and keeps
# SketchUp API work on SketchUp's UI thread, while AgentHostClient owns the
# non-blocking pipe to the persistent Python Agent Host. There is no local
# transcript store, or model/provider integration in this file.

require 'json'
require 'fileutils'
require 'time'
require 'digest'
require 'securerandom'
require_relative 'agent_host_client'

module AI_DG
  module Bridge
    module ControlCenter
      module_function

      ROOT = 'E:/AI-DG'
      SOURCE_STATE_PATH = File.join(ROOT, 'OUTPUT', 'runtime', 'project-state.json')

      def open
        dialog = current_dialog || build_dialog
        agent_host.start
        dialog.show
        push_runtime
        dialog
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center open', e) if Bridge.respond_to?(:log_exception, true)
        nil
      end

      def current_dialog
        @dialog
      end

      def agent_state
        @agent_state || 'IDLE'
      end

      def build_dialog
        html_path = File.join(__dir__, 'ui', 'control_center.html')
        raise LoadError, "Missing AI-DG Control Center UI: #{html_path}" unless File.file?(html_path)

        @dialog = UI::HtmlDialog.new(
          dialog_title: 'AI-DG SketchUp Workspace',
          preferences_key: 'AI-DG SketchUp Workspace',
          scrollable: true,
          resizable: true,
          width: 1120,
          height: 760,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
        @dialog_ready = false
        @dialog.set_file(html_path)
        register_callbacks(@dialog)
        owned_dialog = @dialog
        @dialog.set_on_closed { close_session if @dialog.equal?(owned_dialog) }
        start_runtime_timer
        @dialog
      end

      def register_callbacks(dialog)
        dialog.add_action_callback('ai_dg_ready') do |_context, _payload|
          next unless @dialog.equal?(dialog)

          @dialog_ready = true
          agent_host.start
          push_runtime
        end

        dialog.add_action_callback('ai_dg_action') do |_context, payload|
          next unless @dialog.equal?(dialog) && @dialog_ready

          request = parse_payload(payload)
          response = handle_action(request)
          send_to_ui('aiDgReceive', response) if response
        end

      end

      def agent_host
        @agent_host ||= AI_DG::Bridge::AgentHostClient.new(ROOT)
      end

      def close_session
        @dialog_ready = false
        stop_runtime_timer
        @agent_state = 'IDLE'
        @agent_request_id = nil
        @active_turns = {}
        agent_host.stop
        Bridge.instance_variable_set(:@active_skill, nil)
        Bridge.instance_variable_set(:@current_task, nil)
        @dialog = nil
      end

      def refresh_document
        @dialog_ready = false
        @dialog.set_file(File.join(__dir__, 'ui', 'control_center.html')) if @dialog
        true
      end

      def handle_action(request)
        request = request.is_a?(Hash) ? request : {}
        action = request['action'].to_s
        data = request['data'].is_a?(Hash) ? request['data'] : {}
        case action
        when 'set_mode'
          mode = data['mode'].to_s
          return { status: 'error', action: action, error: 'INVALID_MODE' } unless %w[read_only write_enabled].include?(mode)

          Bridge.set_access_mode(mode)
          { status: 'ok', action: action, data: runtime_payload }
        when 'agent_host_status'
          agent_host.request('host/status')
          accepted_action(action, 'host/status')
        when 'agent_open'
          start_agent_backend(data)
        when 'agent_session_open'
          open_agent_session(data, false)
        when 'agent_session_resume'
          open_agent_session(data, true)
        when 'agent_set_mode'
          agent_host.request('session/set_mode', backend: 'cline', document_key: document_key(data), cwd: safe_cwd(data['cwd']), data: data)
          accepted_action(action, 'session/set_mode')
        when 'agent_turn_start'
          start_agent_turn(data)
        when 'agent_turn_cancel'
          cancel_agent_turn(data)
        when 'agent_approval'
          respond_agent_approval(data)
        when 'agent_model_list'
          request_agent_model_list(data)
        when 'agent_session_close'
          close_agent_session(data)
        when 'agent_cancel'
          cancel_agent_turn(data)
        when 'agent_pause', 'agent_resume'
          { status: 'error', action: action, error: 'PAUSE_RESUME_NOT_SUPPORTED_BY_NATIVE_RUNTIME' }
        when 'pipeline_status'
          pipeline_status.merge(action: action)
        when 'source_folder_select'
          select_source_folder.merge(action: action)
        when 'source_folder_status'
          { status: 'ok', action: action, data: project_state }
        when 'plugin_diagnostics'
          { status: 'ok', action: action, data: { plugins: Bridge.plugin_catalog_snapshot, reload_policy: 'manual_and_graceful_only', dangerous_permissions_default: false, agent_host: agent_host.snapshot } }
        when 'model_select'
          { status: 'error', action: action, error: 'MODEL_SELECTION_OWNED_BY_NATIVE_RUNTIME' }
        when 'load_skill'
          load_skill(data['skill_id'].to_s, data['max_chars']).merge(action: action)
        when 'plugin_set_enabled'
          set_plugin_enabled(data['plugin_id'].to_s, data['enabled']).merge(action: action)
        when 'plugin_reload'
          reload_plugin(data['plugin_id'].to_s).merge(action: action)
        when 'open_file'
          open_developer_file(data['path'].to_s).merge(action: action)
        when 'open_developer_mode'
          { status: 'error', action: action, error: 'DEVELOPER_MODE_IS_STARTUP_CONTROLLED' }
        else
          result = Bridge.dispatch({ 'action' => action, 'data' => data, 'request_id' => request['request_id'] })
          result = result.is_a?(Hash) ? result : { status: 'ok', data: result }
          result.merge(action: action)
        end
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center action', e) if Bridge.respond_to?(:log_exception, true)
        { status: 'error', action: action, error: "#{e.class}: #{e.message}" }
      end

      def start_agent_backend(data)
        backend = normalize_backend(data['backend'])
        return { status: 'error', action: 'agent_open', error: 'INVALID_BACKEND' } unless backend

        request_id = agent_host.request('agent/open', backend: backend, cwd: safe_cwd(data['cwd']))
        accepted_action('agent_open_accepted', 'agent/open', backend: backend, request_id: request_id)
      end

      def open_agent_session(data, resume)
        backend = normalize_backend(data['backend'])
        return { status: 'error', action: resume ? 'agent_session_resume' : 'agent_session_open', error: 'INVALID_BACKEND' } unless backend

        request_id = agent_host.request(resume ? 'session/resume' : 'session/open',
                                        backend: backend,
                                        document_key: document_key(data),
                                        cwd: safe_cwd(data['cwd']),
                                        data: data)
        accepted_action(resume ? 'agent_session_resume_accepted' : 'agent_session_open_accepted', resume ? 'session/resume' : 'session/open', backend: backend, request_id: request_id)
      end

      def start_agent_turn(data)
        backend = normalize_backend(data['backend']) || 'codex'
        text = data['text'].to_s.strip
        return { status: 'error', action: 'agent_turn_start', error: 'EMPTY_PROMPT' } if text.empty?
        return { status: 'error', action: 'agent_turn_start', error: 'INVALID_BACKEND' } unless %w[codex cline].include?(backend)
        return { status: 'blocked', action: 'agent_turn_start', error: 'WRITE_MODE_REQUIRED' } if data['write_requested'] == true && Bridge.access_mode.to_s != 'write_enabled'

        request_id = agent_host.request('turn/start',
                                        backend: backend,
                                        document_key: document_key(data),
                                        cwd: safe_cwd(data['cwd']),
                                        text: text,
                                        data: data)
        @agent_state = 'RUNNING'
        @agent_request_id = request_id
        @active_turns ||= {}
        @active_turns[backend] = request_id
        Bridge.instance_variable_set(:@current_task, text[0, 120])
        Bridge.record_event('agent_turn_started', { backend: backend, request_id: request_id, status: 'RUNNING', stage: 'AGENT' })
        { status: 'ok', action: 'agent_turn_accepted', data: { request_id: request_id, backend: backend, document_key: document_key(data), mode: Bridge.access_mode, implementation_state: 'NATIVE_RUNTIME' } }
      end

      def cancel_agent_turn(data)
        backend = normalize_backend(data['backend']) || @active_turns&.keys&.first || 'codex'
        request_id = agent_host.request('turn/cancel',
                                        backend: backend,
                                        document_key: document_key(data),
                                        cwd: safe_cwd(data['cwd']),
                                        data: data)
        @agent_state = 'CANCELLING'
        accepted_action('agent_cancel_accepted', 'turn/cancel', backend: backend, request_id: request_id)
      end

      def respond_agent_approval(data)
        backend = normalize_backend(data['backend'])
        return { status: 'error', action: 'agent_approval', error: 'INVALID_BACKEND' } unless backend

        request_id = agent_host.request('approval/respond', backend: backend, data: data)
        accepted_action('agent_approval_accepted', 'approval/respond', backend: backend, request_id: request_id)
      end

      def request_agent_model_list(data)
        backend = normalize_backend(data['backend'])
        return { status: 'error', action: 'agent_model_list', error: 'INVALID_BACKEND' } unless backend

        request_id = agent_host.request('model/list', backend: backend, document_key: document_key(data), cwd: safe_cwd(data), data: data)
        accepted_action('agent_model_list_accepted', 'model/list', backend: backend, request_id: request_id)
      end

      def close_agent_session(data)
        backend = normalize_backend(data['backend'])
        return { status: 'error', action: 'agent_session_close', error: 'INVALID_BACKEND' } unless backend

        request_id = agent_host.request('session/close', backend: backend, document_key: document_key(data), data: data)
        @active_turns.delete(backend) if @active_turns
        accepted_action('agent_session_close_accepted', 'session/close', backend: backend, request_id: request_id)
      end

      def process_agent_host_messages
        agent_host.poll.each do |message|
          if message['type'].to_s == 'agent/event'
            process_agent_event(message)
          elsif message['id']
            process_agent_response(message)
          end
        end
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center agent host poll', e) if Bridge.respond_to?(:log_exception, true)
        send_to_ui('aiDgReceive', { status: 'error', action: 'agent_host_error', error: 'AGENT_HOST_POLL_FAILED', detail: e.class.name })
      end

      def process_agent_event(message)
        backend = message['backend'].to_s
        event = message['event'].to_s
        if %w[turn/completed turn/failed turn/interrupted turn/aborted runtime/exited].include?(event)
          @active_turns.delete(backend) if @active_turns
          @agent_state = 'IDLE' if @active_turns.nil? || @active_turns.empty?
          Bridge.instance_variable_set(:@current_task, nil) if @agent_state == 'IDLE'
        elsif event == 'server/request'
          @agent_state = 'WAITING_APPROVAL'
        end
        Bridge.record_event('agent_host_event', { backend: backend, event: event, status: 'INFO', stage: 'AGENT' })
        send_to_ui('aiDgReceive', { status: 'ok', action: 'agent_event', data: message })
      end

      def process_agent_response(message)
        data = message['data'].is_a?(Hash) ? message['data'] : {}
        @agent_state = 'IDLE' if %w[agent_cancel_accepted agent_session_close_accepted].include?(message['action'].to_s)
        send_to_ui('aiDgReceive', { status: 'error', action: 'agent_response', data: message }) if message['status'].to_s == 'error'
        send_to_ui('aiDgReceive', { status: 'ok', action: 'agent_response', data: message }) unless message['status'].to_s == 'error'
      end

      def runtime_payload
        snapshot = Bridge.runtime_snapshot
        snapshot = snapshot.is_a?(Hash) ? snapshot.dup : {}
        snapshot[:agent_host] = agent_host.snapshot
        snapshot[:agent_state] = agent_state
        snapshot
      rescue StandardError => e
        { agent_host: agent_host.snapshot, agent_state: agent_state, error: e.class.name }
      end

      def push_runtime
        return unless @dialog

        process_agent_host_messages
        send_to_ui('aiDgReceive', { status: 'ok', action: 'runtime', data: runtime_payload })
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center push runtime', e) if Bridge.respond_to?(:log_exception, true)
      end

      def start_runtime_timer
        return if @runtime_timer_id

        @runtime_timer_id = UI.start_timer(0.25, true) { push_runtime }
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center runtime timer', e) if Bridge.respond_to?(:log_exception, true)
      end

      def stop_runtime_timer
        UI.stop_timer(@runtime_timer_id) if @runtime_timer_id
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center stop timer', e) if Bridge.respond_to?(:log_exception, true)
      ensure
        @runtime_timer_id = nil
      end

      def parse_payload(payload)
        return payload if payload.is_a?(Hash)

        JSON.parse(payload.to_s)
      rescue JSON::ParserError
        {}
      end

      def send_to_ui(function_name, payload)
        return unless @dialog && @dialog_ready

        json = JSON.generate(payload)
        @dialog.execute_script("window.#{function_name}(#{json});")
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center send ui', e) if Bridge.respond_to?(:log_exception, true)
      end

      def accepted_action(action, native_method, metadata = {})
        { status: 'ok', action: action, data: metadata.merge(native_method: native_method, implementation_state: 'NATIVE_RUNTIME') }
      end

      def normalize_backend(value)
        backend = value.to_s.strip.downcase
        %w[codex cline].include?(backend) ? backend : nil
      end

      def safe_cwd(value)
        candidate = value.to_s.strip
        candidate = project_state['project_root'].to_s if candidate.empty?
        candidate = ROOT if candidate.empty?
        expanded = File.expand_path(candidate)
        File.directory?(expanded) ? expanded : ROOT
      rescue StandardError
        ROOT
      end

      def document_key(data)
        model = Sketchup.active_model
        unless @document_model.equal?(model)
          @document_model = model
          @unsaved_document_id = SecureRandom.uuid
        end
        path = model.path.to_s
        identity = path.empty? ? @unsaved_document_id : File.expand_path(path)
        Digest::SHA256.hexdigest("#{identity}|#{safe_cwd(data['cwd'])}")
      rescue StandardError
        'untitled'
      end

      def project_state
        return {} unless File.file?(SOURCE_STATE_PATH)

        payload = JSON.parse(File.read(SOURCE_STATE_PATH, encoding: 'UTF-8'))
        payload.is_a?(Hash) ? payload : {}
      rescue StandardError
        {}
      end

      def select_source_folder
        selected = UI.select_directory(title: 'Chọn thư mục dự án / bản vẽ AI-DG')
        return { status: 'blocked', error: 'SOURCE_FOLDER_NOT_SELECTED' } if selected.to_s.empty?

        path = File.expand_path(selected.to_s)
        FileUtils.mkdir_p(File.dirname(SOURCE_STATE_PATH))
        File.write(SOURCE_STATE_PATH, JSON.pretty_generate({ 'schema_version' => 1, 'project_root' => path, 'updated_utc' => Time.now.utc.iso8601(3) }), mode: 'w', encoding: 'UTF-8')
        { status: 'ok', data: project_state }
      rescue StandardError => e
        { status: 'error', error: "SOURCE_FOLDER_SAVE_FAILED: #{e.class}: #{e.message}" }
      end

      def pipeline_status
        root = 'E:/AI-DG/WORK/pipeline'
        runs = Dir.glob(File.join(root, '*', 'run-summary.json')).select { |path| File.file?(path) }
        latest = runs.max_by { |path| File.mtime(path) }
        return { status: 'ok', data: { pipeline: 'AI-DG 2D→3D', status: 'NOT_RUN', root: root, runs: 0 } } unless latest

        payload = JSON.parse(File.read(latest, encoding: 'UTF-8'))
        artifacts = payload.is_a?(Hash) ? (payload['artifacts'] || {}) : {}
        review = artifacts['review_queue'] || {}
        plan = artifacts['build_plan'] || {}
        {
          status: 'ok',
          data: {
            pipeline: 'AI-DG 2D→3D',
            status: payload['status'] || 'DONE',
            gate_status: payload['gate_status'] || 'REVIEW_REQUIRED',
            run_id: payload['run_id'],
            generated_utc: payload['generated_utc'],
            package_count: payload['package_count'].to_i,
            drawing_count: Array(artifacts.dig('index', 'entries')).length,
            dimension_count: Array(artifacts.dig('dimension_graph', 'nodes')).length,
            material_count: Array(artifacts.dig('material_graph', 'materials')).length,
            review_status: review['status'] || 'OPEN',
            review_items: Array(review['items']).first(100),
            build_operations: Array(plan['operations']).first(100),
            blocked_items: Array(plan['blocked_items']).first(100),
            artifact_summary: latest
          }
        }
      rescue StandardError => e
        { status: 'error', error: "PIPELINE_STATUS_READ_FAILED: #{e.class}: #{e.message}" }
      end

      def load_skill(skill_id, max_chars = nil)
        return { status: 'error', error: 'INVALID_SKILL_ID' } unless skill_id.match?(/\A[A-Za-z0-9._-]+\z/)

        limit = [[max_chars.to_i.zero? ? 6000 : max_chars.to_i, 500].max, 12_000].min
        path = [File.join(ROOT, 'skills'), File.join(ROOT, '.agents', 'skills')].map { |root| File.join(root, skill_id, 'SKILL.md') }.find { |candidate| File.file?(candidate) }
        return { status: 'error', error: 'SKILL_NOT_FOUND', skill_id: skill_id } unless path

        Bridge.record_event('skill_loaded', { skill: skill_id, status: 'SUCCESS' })
        { status: 'ok', skill_id: skill_id, source: path, content: File.read(path, encoding: 'UTF-8')[0, limit], truncated: File.size(path) > limit }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}", skill_id: skill_id }
      end

      def set_plugin_enabled(plugin_id, enabled)
        return { status: 'error', error: 'INVALID_PLUGIN_ID' } unless plugin_id.match?(/\A[A-Za-z0-9._-]+\z/)
        return { status: 'error', error: 'CORE_PLUGIN_CANNOT_BE_DISABLED' } if plugin_id == 'ai-dg-core' && !enabled

        known = plugin_id == 'ai-dg-core' || File.file?(File.join(ROOT, 'plugins', plugin_id, 'manifest.json'))
        return { status: 'error', error: 'PLUGIN_NOT_FOUND', plugin_id: plugin_id } unless known

        path = File.join(ROOT, 'OUTPUT', 'runtime', 'plugin-state.json')
        state = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        state[plugin_id] = { 'enabled' => !!enabled }
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate(state), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('plugin_changed', { plugin: plugin_id, enabled: !!enabled, status: 'SUCCESS' })
        { status: 'ok', plugin_id: plugin_id, enabled: !!enabled, persistence_path: path }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}", plugin_id: plugin_id }
      end

      def reload_plugin(plugin_id)
        return { status: 'error', error: 'INVALID_PLUGIN_ID' } unless plugin_id.match?(/\A[A-Za-z0-9._-]+\z/)
        known = plugin_id == 'ai-dg-core' || File.file?(File.join(ROOT, 'plugins', plugin_id, 'manifest.json'))
        return { status: 'error', error: 'PLUGIN_NOT_FOUND', plugin_id: plugin_id } unless known

        Bridge.record_event('plugin_reload_queued', { plugin: plugin_id, status: 'SUCCESS', policy: 'manual_and_graceful_only' })
        { status: 'ok', plugin_id: plugin_id, reload: 'QUEUED_GRACEFUL', policy: 'manual_and_graceful_only' }
      end

      def open_developer_file(path)
        root = File.expand_path(ROOT).tr('\\', '/')
        candidate = File.expand_path(path.to_s).tr('\\', '/')
        return { status: 'error', error: 'DEVELOPER_FILE_OUTSIDE_WORKSPACE' } unless candidate == root || candidate.start_with?("#{root}/")
        return { status: 'error', error: 'DEVELOPER_FILE_NOT_FOUND', path: candidate } unless File.file?(candidate)

        UI.openURL("file:///#{candidate}")
        { status: 'ok', path: candidate }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end
    end
  end
end

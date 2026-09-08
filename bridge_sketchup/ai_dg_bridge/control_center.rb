# frozen_string_literal: true

# AI-DG MCP-SU Control Center.
#
# The dialog is deliberately local: it is loaded from the installed plugin
# folder and talks to SketchUp only through action callbacks.  It does not
# open a browser, make network requests, or modify another plugin's UI.

require 'json'
require 'fileutils'
require 'digest'
require 'time'
require 'uri'
require 'open3'
require_relative 'helper_process'

module AI_DG
  module Bridge
    module ControlCenter
      module_function

      def open
        dialog = current_dialog || build_dialog
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
          dialog_title: 'AI-DG MCP-SU Control Center',
          preferences_key: 'AI-DG MCP-SU Control Center',
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
          push_runtime
        end

        dialog.add_action_callback('ai_dg_action') do |_context, payload|
          next unless @dialog.equal?(dialog) && @dialog_ready
          request = parse_payload(payload)
          response = handle_action(request)
          send_to_ui('aiDgReceive', response)
        end

        dialog.add_action_callback('ai_dg_chat') do |_context, payload|
          next unless @dialog.equal?(dialog) && @dialog_ready
          request = parse_payload(payload)
          response = start_chat_job(request['message'].to_s)
          send_to_ui('aiDgReceive', response)
        end
      end

      def helper_busy?
        !!(@helper_job && @helper_job.active?)
      end

      def busy?
        !!(@chat_job || @provider_job || helper_busy?)
      end

      def close_session
        @dialog_ready = false
        @helper_job.cancel if @helper_job
        stop_runtime_timer
        stop_agent_job_timer
        @chat_job = @provider_job = nil
        @agent_cancel_requested = false
        @agent_state = 'IDLE'
        @agent_request_id = nil
        Bridge.instance_variable_set(:@active_skill, nil)
        Bridge.instance_variable_set(:@current_task, nil)
        @dialog = nil
      end

      def refresh_document
        return false if busy?
        @dialog_ready = false
        @dialog.set_file(File.join(__dir__, 'ui', 'control_center.html')) if @dialog
        true
      end

      def handle_action(request)
        action = request['action'].to_s
        case action
        when 'set_mode'
          mode = request.dig('data', 'mode').to_s
          return { status: 'error', error: 'Invalid mode' } unless %w[read_only write_enabled].include?(mode)

          Bridge.set_access_mode(mode)
          { status: 'ok', action: action, data: Bridge.runtime_snapshot }
        when 'agent_cancel', 'agent_pause', 'agent_resume', 'agent_status'
          agent_control(action)
        when 'agent_backend_status'
          agent_backend_status.merge(action: action)
        when 'agent_backend_select'
          set_agent_backend(request.dig('data', 'backend').to_s).merge(action: action)
        when 'provider_audit'
          start_provider_job(action, {})
        when 'pipeline_status'
          pipeline_status.merge(action: action)
        when 'provider_configure'
          start_provider_job(action, request['data'] || {})
        when 'provider_test', 'provider_sync'
          start_provider_job(action, request['data'] || {})
        when 'provider_disconnect'
          start_provider_job(action, {})
        when 'provider_network_enable'
          set_provider_network(true).merge(action: action)
        when 'provider_network_disable'
          set_provider_network(false).merge(action: action)
        when 'codex_network_enable'
          set_agent_backend_network(true).merge(action: action)
        when 'codex_network_disable'
          set_agent_backend_network(false).merge(action: action)
        when 'model_status'
          model_manager_status.merge(action: action)
        when 'model_select'
          return { status: 'blocked', action: action, error: 'PROVIDER_JOB_BUSY' } if busy?
          set_model(request.dig('data', 'model').to_s).merge(action: action)
        when 'plugin_diagnostics'
          { status: 'ok', action: action, data: { plugins: Bridge.plugin_catalog_snapshot, reload_policy: 'manual_and_graceful_only', dangerous_permissions_default: false } }
        when 'load_skill'
          load_skill(request.dig('data', 'skill_id').to_s, request.dig('data', 'max_chars')).merge(action: action)
        when 'plugin_set_enabled'
          set_plugin_enabled(request.dig('data', 'plugin_id').to_s, request.dig('data', 'enabled')).merge(action: action)
        when 'plugin_reload'
          reload_plugin(request.dig('data', 'plugin_id').to_s).merge(action: action)
        when 'open_file'
          open_developer_file(request.dig('data', 'path').to_s).merge(action: action)
        when 'open_developer_mode'
          { status: 'error', error: 'Developer mode is controlled by AI_DG_DEVELOPER_MODE=1 before startup.' }
        else
          result = Bridge.dispatch({ 'action' => action, 'data' => request['data'] || {} })
          result = result.is_a?(Hash) ? result : { status: 'ok', data: result }
          result.merge(action: action)
        end
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center action', e) if Bridge.respond_to?(:log_exception, true)
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end

      # Chat is a small UI-thread state machine rather than one long callback.
      # That gives Pause/Resume/Cancel a chance to take effect between the
      # bounded agent phases while keeping every SketchUp API call on the UI
      # thread (SketchUp's Ruby API is not thread-safe).
      def start_chat_job(message)
        prompt = message.strip
        return { status: 'error', error: 'Tin nhắn trống' } if prompt.empty?

        return { status: 'blocked', action: 'chat', error: 'AGENT_BUSY', request_id: new_id('agent'), session_id: current_session_id } if busy?
        request_id = new_id('agent')
        session_id = current_session_id
        return { status: 'blocked', action: 'chat', error: 'AGENT_PAUSED', request_id: request_id, session_id: session_id } if @agent_state.to_s == 'PAUSED'
        backend = agent_backend_name

        # User Mode uses the real provider helper.  The explicit local toggle
        # is required before a network request; the child process receives the
        # permission for this request only and no background retry is used.
        unless Bridge::DEVELOPER_MODE
          network_enabled = backend == 'codex_cli' ? codex_network_enabled? : provider_network_enabled?
          unless network_enabled
            if backend == 'codex_cli'
              return {
                status: 'blocked',
                action: 'chat',
                error: 'CODEX_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE',
                provider_status: 'NOT_VERIFIED',
                message: 'Hãy bấm “Cho phép Codex CLI” trước khi chat; Codex và 9Router dùng quyền network riêng.'
              }
            end
            return {
              status: 'blocked',
              action: 'chat',
              error: 'PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE',
              provider_status: 'NOT_VERIFIED',
              message: 'Hãy bấm “Cho phép gọi provider” trước khi chat; AI-DG không dùng fallback trả lời cố định.'
            }
          end
          if backend == 'codex_cli'
            unless codex_cli_available?
              return { status: 'blocked', action: 'chat', error: 'CODEX_CLI_NOT_FOUND', request_id: request_id, session_id: session_id, message: 'Không tìm thấy Codex CLI trên máy.' }
            end
          end

          @agent_state = 'RUNNING'
          @agent_cancel_requested = false
          @agent_request_id = request_id
          @current_task = prompt[0, 120]
          Bridge.instance_variable_set(:@current_task, @current_task)
          @chat_job = {
            prompt: prompt,
            provider_prompt: conversation_prompt(prompt),
            request_id: request_id,
            session_id: session_id,
            phase: backend == 'codex_cli' ? 'codex_wait' : 'provider_wait',
            intent: backend == 'codex_cli' ? :codex : :provider,
            backend: backend,
            result: nil,
            provider_done: false
          }
          if backend == 'codex_cli'
            start_codex_cli_thread(@chat_job)
          else
            start_provider_chat_thread(@chat_job)
          end
          start_agent_job_timer
          return { status: 'ok', action: 'chat_started', data: { request_id: request_id, session_id: session_id, agent_state: @agent_state, backend: backend, max_steps: 2, max_tool_calls: 1, implementation_state: 'REAL' } }
        end

        # Developer Mode may exercise the bounded local diagnostic harness,
        # explicitly labelled as DEV_MOCK in its response and trace.
        @agent_state = 'RUNNING'
        @agent_cancel_requested = false
        @agent_request_id = request_id
        @current_task = prompt[0, 120]
        Bridge.instance_variable_set(:@current_task, @current_task)
        Bridge.record_event('agent_started', {
          request_id: request_id,
          session_id: session_id,
          status: 'RUNNING',
          stage: 'AGENT',
          prompt_sha256: Digest::SHA256.hexdigest(prompt)[0, 16],
          prompt_length: prompt.length,
          max_steps: 2,
          max_tool_calls: 1
        })
        @chat_job = {
          prompt: prompt,
          request_id: request_id,
          session_id: session_id,
          phase: 'classify',
          intent: nil,
          skill_id: nil,
          tool: nil,
          result: nil
        }
        start_agent_job_timer
        { status: 'ok', action: 'chat_started', data: { request_id: request_id, session_id: session_id, agent_state: @agent_state, max_steps: 2, max_tool_calls: 1 } }
      rescue StandardError => e
        { status: 'error', action: 'chat', error: "#{e.class}: #{e.message}", request_id: request_id, session_id: session_id }
      end

      def start_agent_job_timer
        return if @agent_timer_id

        # SketchUp's repeating timer can coalesce very short callbacks while
        # the HtmlDialog is active.  Use a small UI heartbeat and enforce the
        # actual bounded phase interval in Ruby so controls remain observable.
        @agent_next_step_at = Time.now.to_f + agent_step_interval
        @agent_timer_id = UI.start_timer(0.05, true) { process_chat_job }
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center agent timer', e) if Bridge.respond_to?(:log_exception, true)
        finish_chat_job(@chat_job, "AGENT_TIMER_FAILED: #{e.message}") if @chat_job
      end

      def stop_agent_job_timer
        UI.stop_timer(@agent_timer_id) if @agent_timer_id
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center stop agent timer', e) if Bridge.respond_to?(:log_exception, true)
      ensure
        @agent_timer_id = nil
        @agent_next_step_at = nil
      end

      # Optional local failure/interaction harness.  It is absent in normal
      # installs, and the bounded clamp keeps a test file from turning the
      # agent into an unbounded polling loop.
      def agent_step_interval
        path = 'E:/AI-DG/OUTPUT/runtime/agent-test-config.json'
        return 0.08 unless File.file?(path)

        payload = JSON.parse(File.read(path, encoding: 'UTF-8'))
        delay_ms = payload.is_a?(Hash) ? payload['step_delay_ms'].to_f : 80.0
        [[delay_ms, 80.0].max, 2000.0].min / 1000.0
      rescue StandardError
        0.08
      end

      def process_chat_job
        job = @chat_job
        return stop_agent_job_timer unless job
        return if @agent_state.to_s == 'PAUSED' && !@agent_cancel_requested

        if @agent_cancel_requested
          job[:worker].cancel if job[:worker]
          return if job[:worker] && job[:worker].active?
          finish_chat_job(job, 'AGENT_CANCELLED')
          return
        end

        if %w[provider_wait codex_wait].include?(job[:phase])
          result = job[:worker] && job[:worker].result
          return unless result
          job[:result] = result

          finish_chat_job(job)
          return
        end
        return if Time.now.to_f < @agent_next_step_at.to_f

        @agent_next_step_at = Time.now.to_f + agent_step_interval

        case job[:phase]
        when 'classify'
          lowered = job[:prompt].downcase
          job[:intent] = if lowered.include?('kích thước') || lowered.include?('kích thuoc') || lowered.include?('dimension')
                           :dimensions
                         elsif lowered.include?('tên') || lowered.include?('name') || lowered.include?('model')
                           :model
                         elsif lowered.include?('chọn') || lowered.include?('selection') || lowered.include?('đối tượng') || lowered.include?('cái này')
                           :selection
                         else
                           :general
                         end
          if job[:intent] == :dimensions
            job[:skill_id] = 'ai-dg-selection-reader'
            Bridge.instance_variable_set(:@active_skill, job[:skill_id])
            job[:phase] = 'skill_start'
          elsif job[:intent] == :model
            job[:tool] = 'sketchup_get_model_summary'
            job[:phase] = 'tool'
          elsif job[:intent] == :selection
            job[:tool] = 'sketchup_get_selection'
            job[:phase] = 'tool'
          else
            job[:result] = { status: 'ok', data: { mode: Bridge.access_mode, next_tool: 'sketchup_get_model_summary' } }
            job[:phase] = 'finish'
          end
        when 'skill_start'
          Bridge.record_event('skill_started', { request_id: job[:request_id], session_id: job[:session_id], skill: job[:skill_id], status: 'RUNNING', stage: 'SKILL' })
          job[:phase] = 'skill_load'
        when 'skill_load'
          skill = load_skill(job[:skill_id], 6000)
          if skill[:status].to_s != 'ok' && skill['status'].to_s != 'ok'
            job[:result] = { status: 'error', error: 'SKILL_LOAD_FAILED' }
            job[:phase] = 'skill_finish'
          else
            Bridge.record_event('skill_loaded', { request_id: job[:request_id], session_id: job[:session_id], skill: job[:skill_id], status: 'SUCCESS', stage: 'SKILL' })
            job[:tool] = 'sketchup_get_selection'
            job[:phase] = 'tool'
          end
        when 'tool'
          job[:result] = Bridge.dispatch('action' => job[:tool] == 'sketchup_get_model_summary' ? 'get_model_info' : 'get_selection', 'data' => {}, 'request_id' => "#{job[:request_id]}-tool-1", 'session_id' => job[:session_id])
          job[:phase] = job[:skill_id] ? 'skill_finish' : 'finish'
        when 'skill_finish'
          Bridge.record_event('skill_finished', { request_id: job[:request_id], session_id: job[:session_id], skill: job[:skill_id], status: result_status(job[:result]) == 'ok' ? 'SUCCESS' : 'ERROR', stage: 'SKILL', error: result_status(job[:result]) == 'ok' ? nil : (job[:result][:error] || job[:result]['error']) })
          job[:phase] = 'finish'
        when 'finish'
          finish_chat_job(job)
        end
      rescue StandardError => e
        finish_chat_job(job, "#{e.class}: #{e.message}") if job
      end

      def finish_chat_job(job, forced_error = nil)
        return unless job && @chat_job.equal?(job)
        job[:worker].cancel if forced_error && job[:worker]

         result = if forced_error
                   { status: 'blocked', error: forced_error }
                 else
                   job[:result] || { status: 'error', error: 'AGENT_NO_RESULT' }
                 end
         real_provider = %w[provider_wait codex_wait].include?(job[:phase]) || %i[provider codex].include?(job[:intent])
         ok = !forced_error && result_status(result) == 'ok'
         answer = if forced_error
                    forced_error == 'AGENT_CANCELLED' ? 'Agent đã dừng theo yêu cầu.' : "Agent dừng vì lỗi: #{forced_error}"
                  elsif real_provider
                    result['answer'] || result[:answer] || result['message'] || result[:message] || "Provider không trả lời: #{result['error'] || result[:error] || 'UNKNOWN_PROVIDER_ERROR'}"
                  else
                   format_chat_answer(job[:intent], result)
                  end
         result_tool = result['tool'] || result[:tool] || job[:tool]
         result_steps = result['steps'] || result[:steps]
         result_tool_calls = result['tool_calls'] || result[:tool_calls]
         result_request_count = result['request_count'] || result[:request_count]
         agent_status = forced_error ? 'BLOCKED' : (ok ? 'SUCCESS' : (real_provider ? 'BLOCKED' : 'ERROR'))
         Bridge.record_event('agent_finished', { request_id: job[:request_id], session_id: job[:session_id], status: agent_status, stage: 'AGENT', tool: result_tool, skill: job[:skill_id], max_steps: 2, max_tool_calls: result_tool ? 1 : 0, provider_request_count: result_request_count, error: forced_error || (!ok ? (result[:error] || result['error']) : nil) })
         response = { status: ok ? 'ok' : (forced_error || real_provider ? 'blocked' : 'error'), action: 'chat', data: { prompt: job[:prompt], answer: answer, details: result, backend: job[:backend] || 'local', provider_status: result['provider_state'] || result[:provider_state] || result['status'], model: result['model'], tool: result_tool, skill: job[:skill_id], steps: result_steps, tool_calls: result_tool_calls, request_count: result_request_count, mcp_server: result['mcp_server'] || result[:mcp_server], request_id: job[:request_id], session_id: job[:session_id], mode: Bridge.access_mode, agent_state: agent_status, implementation_state: real_provider ? 'REAL' : 'DEV_MOCK' } }
        persist_chat_message(job[:prompt], answer) if ok
        @chat_job = nil
        stop_agent_job_timer
        @agent_state = 'IDLE' unless @agent_state.to_s == 'PAUSED'
        @agent_cancel_requested = false
        @agent_request_id = nil
        Bridge.instance_variable_set(:@active_skill, nil)
        Bridge.instance_variable_set(:@current_task, nil)
        send_to_ui('aiDgReceive', response)
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center agent finish', e) if Bridge.respond_to?(:log_exception, true)
        @chat_job = nil
        stop_agent_job_timer
        @agent_state = 'IDLE'
      end

      def agent_control(action)
        case action
        when 'agent_cancel'
          if @chat_job
            @agent_cancel_requested = true
            @chat_job[:worker].cancel if @chat_job[:worker]
            @agent_state = 'CANCELLING'
          else
            # A stale cancel click must never cancel the next request.
            @agent_cancel_requested = false
            @agent_state = 'IDLE'
          end
        when 'agent_pause'
          @agent_state = 'PAUSED' if @chat_job
        when 'agent_resume'
          return { status: 'blocked', action: action, error: 'AGENT_CANCELLING' } if @agent_cancel_requested
          @agent_cancel_requested = false
          @agent_next_step_at = Time.now.to_f + agent_step_interval if @chat_job
          @agent_state = @chat_job ? 'RUNNING' : 'IDLE'
        end
        { status: 'ok', action: action, data: { agent_state: @agent_state || 'IDLE', request_id: @agent_request_id, cancel_requested: !!@agent_cancel_requested } }
      end

      def result_status(result)
        (result[:status] || result['status']).to_s
      end

      def format_chat_answer(intent, result)
        return "Không thể đọc SketchUp: #{result[:error] || result['error'] || 'unknown error'}" unless result_status(result) == 'ok'

        data = result[:data] || result['data'] || {}
        case intent
        when :model
          title = data[:title] || data['title']
          title = '(Untitled — chưa lưu)' if title.to_s.empty?
          path = data[:path] || data['path']
          path = '(chưa lưu)' if path.to_s.empty?
          "Model đang mở: #{title}. Entities: #{data[:entities] || data['entities'] || 0}; bounds: #{Array(data[:bounds_mm] || data['bounds_mm']).join(' × ')} mm; path: #{path}."
        when :dimensions
          items = data[:items] || data['items'] || []
          return 'Không có đối tượng nào đang được chọn.' if items.empty?
          return "Đang chọn #{items.length} đối tượng; cần chọn đúng một đối tượng để đọc kích thước." unless items.length == 1

          item = items.first
          name = item[:name] || item['name']
          name = '(không có tên)' if name.to_s.empty?
          bounds = item[:bounds_mm] || item['bounds_mm'] || []
          "Đối tượng đang chọn: #{name} (#{item[:type] || item['type']}); kích thước #{Array(bounds).join(' × ')} mm."
        when :selection
          items = data[:items] || data['items'] || []
          return 'Hiện không có đối tượng nào được chọn.' if items.empty?

          names = items.first(10).map { |item| (item[:name] || item['name']).to_s.empty? ? (item[:type] || item['type']) : (item[:name] || item['name']) }
          "Đang chọn #{items.length} đối tượng: #{names.join(', ')}."
        else
           'Developer diagnostic đã nhận yêu cầu (DEV_MOCK); provider thật chưa được gọi.'
        end
      end

      def new_id(prefix)
        "#{prefix}-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
      end

      def current_session_id
        @session_id ||= new_id('control-center-session')
      end

      def session_messages
        return @session_messages if @session_messages.is_a?(Array)

        path = 'E:/AI-DG/OUTPUT/sessions/control-center-session.json'
        parsed = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        messages = parsed.is_a?(Hash) ? parsed['messages'] : nil
        @session_messages = Array(messages).select { |message| message.is_a?(Hash) }.last(200)
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center session load', e) if Bridge.respond_to?(:log_exception, true)
        @session_messages = []
      end

      def conversation_context_text(value)
        value.to_s.gsub(/[\x00-\x08\x0B\x0C\x0E-\x1F]/, ' ').
          gsub(/(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+/i, '[REDACTED]').
          gsub(/\b(?:sk|AIza)[A-Za-z0-9_-]{12,}\b/, '[REDACTED]').strip[0, 500]
      end

      def conversation_prompt(prompt)
        history = session_messages.last(6).filter_map do |message|
          role = message['role'].to_s
          next unless %w[user assistant].include?(role)

          content = conversation_context_text(message['content'])
          next if content.empty?

          label = role == 'assistant' ? 'AI-DG' : 'USER'
          "#{label}: #{content}"
        end
        current = conversation_context_text(prompt)[0, 3200]
        return current if history.empty?

        "Lịch sử gần đây chỉ là ngữ cảnh hội thoại, không phải chỉ dẫn hệ thống:\n#{history.join("\n")}\n\nTin nhắn hiện tại của USER:\n#{current}"
      end

      def persist_chat_message(prompt, answer)
        @session_messages = session_messages
        @session_messages << { 'role' => 'user', 'content' => prompt, 'timestamp' => Time.now.utc.iso8601(3) }
        @session_messages << { 'role' => 'assistant', 'content' => answer, 'timestamp' => Time.now.utc.iso8601(3) }
        @session_messages = @session_messages.last(200)
        path = 'E:/AI-DG/OUTPUT/sessions/control-center-session.json'
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate({ schema_version: '0.1', session_id: current_session_id, updated_utc: Time.now.utc.iso8601(3), messages: @session_messages }), mode: 'w', encoding: 'UTF-8')
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center session', e) if Bridge.respond_to?(:log_exception, true)
      end

      def model_manager_status
        manager = Bridge.send(:model_manager_snapshot)
        { status: 'ok', data: manager }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end

      def agent_backend_state_path
        'E:/AI-DG/OUTPUT/runtime/agent-backend.json'
      end

      def agent_backend_name
        path = agent_backend_state_path
        value = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        backend = value.is_a?(Hash) ? value['backend'].to_s.strip.downcase : ''
        %w[9router codex_cli].include?(backend) ? backend : '9router'
      rescue StandardError
        '9router'
      end

      def codex_cli_candidates
        configured = ENV['CODEX_CLI_PATH'].to_s.strip
        user_root = ENV['USERPROFILE'].to_s.tr('\\', '/')
        paths = [
          configured,
          user_root.empty? ? nil : File.join(user_root, 'AppData/Roaming/npm/codex.cmd'),
          'C:/Users/Admin/AppData/Roaming/npm/codex.cmd'
        ].compact.reject(&:empty?)
        local_bin = user_root.empty? ? nil : File.join(user_root, 'AppData/Local/OpenAI/Codex/bin/*/codex.exe')
        paths.concat(Dir.glob(local_bin)) if local_bin
        paths
      end

      def codex_cli_path
        codex_cli_candidates.find { |path| File.file?(path) }
      rescue StandardError
        nil
      end

      def codex_cli_available?
        !codex_cli_path.nil?
      end

      def agent_backend_status
        backend = agent_backend_name
        {
          status: 'ok',
          data: {
            backend: backend,
            label: backend == 'codex_cli' ? 'Codex CLI' : '9Router',
            codex_cli_available: codex_cli_available?,
            codex_cli_runtime: codex_cli_path ? File.basename(codex_cli_path) : nil,
            network_permission: backend == 'codex_cli' ? (codex_network_enabled? ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE') : (provider_network_enabled? ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE')
          }
        }
      rescue StandardError => e
        { status: 'error', error: "AGENT_BACKEND_STATUS_FAILED: #{e.class}: #{e.message}" }
      end

      def set_agent_backend(backend)
        normalized = backend.to_s.strip.downcase
        return { status: 'error', error: 'INVALID_AGENT_BACKEND' } unless %w[9router codex_cli].include?(normalized)

        path = agent_backend_state_path
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate({ 'backend' => normalized, 'updated_utc' => Time.now.utc.iso8601(3) }), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('agent_backend_changed', { backend: normalized, status: 'SUCCESS', stage: 'AGENT' })
        agent_backend_status
      rescue StandardError => e
        { status: 'error', error: "AGENT_BACKEND_WRITE_FAILED: #{e.class}: #{e.message}" }
      end

      def codex_network_enabled?
        path = agent_backend_state_path
        value = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        value.is_a?(Hash) && value['network_enabled'] == true
      rescue StandardError
        false
      end

      def set_agent_backend_network(enabled)
        path = agent_backend_state_path
        value = if File.file?(path)
                  JSON.parse(File.read(path, encoding: 'UTF-8'))
                else
                  {}
                end
        value = {} unless value.is_a?(Hash)
        value['backend'] = agent_backend_name
        value['network_enabled'] = !!enabled
        value['updated_utc'] = Time.now.utc.iso8601(3)
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate(value), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('codex_permission_changed', { enabled: !!enabled, status: 'SUCCESS', stage: 'AGENT' })
        agent_backend_status
      rescue StandardError => e
        { status: 'error', error: "CODEX_PERMISSION_WRITE_FAILED: #{e.class}: #{e.message}" }
      end

      def set_model(model)
        normalized = model.strip
        return { status: 'error', error: 'INVALID_MODEL_ID' } unless normalized.empty? || normalized.match?(/\A[A-Za-z0-9._:\/-]{1,200}\z/)

        path = 'E:/AI-DG/OUTPUT/runtime/model-state.json'
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate({ 'model' => normalized, 'mode' => normalized.empty? ? 'AUTO' : 'MANUAL', 'updated_utc' => Time.now.utc.iso8601(3) }), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('model_changed', { status: 'SUCCESS', model: normalized.empty? ? 'AUTO' : normalized, stage: 'MODEL' })
        { status: 'ok', data: Bridge.send(:model_manager_snapshot) }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end

      def provider_audit
        path = 'E:/api-key.properties'
        last_test = read_provider_state
        return { status: 'ok', data: { provider: '9Router', config_exists: false, credential_present: false, endpoint_candidates: [], network_test: 'NOT_RUN', last_test: last_test, status: 'UNCONFIGURED' } } unless File.file?(path)

        key_present = false
        key_length = 0
        endpoints = []
        File.foreach(path, encoding: 'UTF-8', invalid: :replace, undef: :replace, replace: '') do |raw|
          line = raw.to_s.strip
          key, value = line.split(/[=:]/, 2)
          if key.to_s.match?(/9router|orcarouter|openrouter/i) && value
            cleaned = value.to_s.strip.gsub(/\A["']|["']\z/, '')
            key_present ||= cleaned.length >= 16
            key_length = [key_length, cleaned.length].max
          end
          line.scan(%r{https?://[^\s"']+}i).each do |candidate|
            begin
              parsed = URI.parse(candidate)
              endpoints << "#{parsed.scheme}://#{parsed.host}#{parsed.port && ![80, 443].include?(parsed.port) ? ":#{parsed.port}" : ''}#{parsed.path}"
            rescue URI::InvalidURIError
              next
            end
          end if line.match?(/router|openai|api/i)
        end
        endpoints = endpoints.uniq
        provider_status = if %w[CONNECTED TESTING AUTH_ERROR RATE_LIMITED NO_CREDIT OFFLINE MODEL_ERROR].include?(last_test['status'].to_s)
                            last_test['status'].to_s
                          elsif key_present && !endpoints.empty?
                            'OFFLINE'
                          else
                            'UNCONFIGURED'
                          end
        { status: 'ok', data: { provider: '9Router', config_exists: true, credential_present: key_present, credential_length: key_length, endpoint_candidates: endpoints, network_test: last_test['operation'].to_s == 'test_chat' ? last_test['status'].to_s : 'NOT_RUN', last_test: last_test, status: provider_status } }
      rescue StandardError => e
        { status: 'error', error: "#{e.class}: #{e.message}" }
      end

      def provider_manager_audit
        result = run_provider_helper('action' => 'status')
        if result.is_a?(Hash) && result['status'].to_s == 'ok'
          provider = result['provider'].is_a?(Hash) ? result['provider'] : {}
          model = result['model'].is_a?(Hash) ? result['model'] : {}
          return {
            status: 'ok',
            data: provider.merge(
              'model' => model,
              'network_permission' => provider_network_enabled? ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE'
            )
          }
        end

        fallback = provider_audit
        fallback_data = fallback[:data] || fallback['data'] || {}
        fallback.merge(data: fallback_data.merge(network_permission: provider_network_enabled? ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE'))
      rescue StandardError => e
        { status: 'error', error: "PROVIDER_STATUS_READ_FAILED: #{e.class}: #{e.message}" }
      end

      def provider_configure(data)
        payload = {
          'action' => 'configure',
          'provider_name' => data['provider_name'].to_s[0, 100],
          'provider_type' => data['provider_type'].to_s[0, 60],
          'base_url' => data['base_url'].to_s[0, 500],
          'model_id' => data['model_id'].to_s[0, 200],
          # The key is passed only to the one-shot helper and is never logged
          # or written by Ruby.  provider.py stores it in the OS credential store.
          'api_key' => data['api_key'].to_s[0, 500],
          'enabled' => data.key?('enabled') ? !!data['enabled'] : true
        }
        run_provider_helper(payload)
      rescue StandardError => e
        { status: 'error', error: "PROVIDER_CONFIGURE_FAILED: #{e.class}: #{e.message}" }
      end

      def provider_disconnect
        run_provider_helper('action' => 'disconnect')
      rescue StandardError => e
        { status: 'error', error: "PROVIDER_DISCONNECT_FAILED: #{e.class}: #{e.message}" }
      end

      # Chat must fail before spawning a provider process when the local
      # configuration is incomplete.  This keeps the UI actionable and avoids
      # turning a known MODEL_REQUIRED/API_KEY_REQUIRED result into a generic
      # helper transport error.
      def provider_chat_preflight
        audit = provider_manager_audit
        data = audit[:data] || audit['data'] || {}
        provider_status = data[:status] || data['status'] || 'UNCONFIGURED'
        credential_present = data[:credential_present]
        credential_present = data['credential_present'] if credential_present.nil?
        endpoints = data[:endpoint_candidates] || data['endpoint_candidates'] || []
        model_data = data[:model] || data['model'] || {}
        model = model_data[:configured_model] || model_data['configured_model'] || model_data[:model] || model_data['model']
        model = model.to_s.strip

        unless credential_present
          return {
            status: 'blocked',
            error: '9ROUTER_CREDENTIAL_NOT_FOUND',
            provider_status: provider_status,
            message: 'Chưa thấy API key trong Windows Credential Manager. Hãy lưu lại key trong Cài đặt → 9Router / Provider.'
          }
        end
        if Array(endpoints).empty?
          return {
            status: 'blocked',
            error: '9ROUTER_ENDPOINT_NOT_FOUND',
            provider_status: provider_status,
            message: 'Chưa có Base URL provider hợp lệ. Hãy nhập Base URL OpenAI-compatible rồi lưu lại.'
          }
        end
        unless model.empty? || model == 'AUTO'
          return { status: 'ok', model: model, provider_status: provider_status }
        end

        {
          status: 'blocked',
          error: 'MODEL_REQUIRED',
          provider_status: provider_status,
          message: 'Chưa chọn model. Hãy bấm Sync Models sau khi cho phép gọi provider, hoặc nhập Canonical model ID rồi bấm Lưu model.'
        }
      rescue StandardError => e
        { status: 'blocked', error: 'PROVIDER_PREFLIGHT_FAILED', detail: e.class.name, message: 'Không đọc được cấu hình provider cục bộ; mở Cài đặt và bấm Làm mới.' }
      end

      def provider_network_enabled?
        return @provider_network_enabled unless @provider_network_enabled.nil?

        path = 'E:/AI-DG/OUTPUT/runtime/provider-ui-state.json'
        value = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        @provider_network_enabled = value.is_a?(Hash) && value['enabled'] == true
      rescue StandardError
        @provider_network_enabled = false
      end

      def set_provider_network(enabled)
        @provider_network_enabled = !!enabled
        path = 'E:/AI-DG/OUTPUT/runtime/provider-ui-state.json'
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate({ 'enabled' => @provider_network_enabled, 'updated_utc' => Time.now.utc.iso8601(3) }), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('provider_permission_changed', { enabled: @provider_network_enabled, status: 'SUCCESS' })
        { status: 'ok', data: { network_permission: @provider_network_enabled ? 'ENABLED_FOR_EXPLICIT_ACTIONS' : 'REQUIRES_EXPLICIT_ENABLE', enabled: @provider_network_enabled } }
      rescue StandardError => e
        { status: 'error', error: "PROVIDER_PERMISSION_WRITE_FAILED: #{e.class}: #{e.message}" }
      end

      def start_provider_job(action, data)
        unless provider_network_enabled?
          return {
            status: 'blocked',
            action: action,
            error: 'PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE',
            request_count: 0,
            hint: 'Bấm Cho phép gọi provider trước khi chạy test hoặc sync.'
          }
        end
        return { status: 'blocked', action: action, error: 'PROVIDER_JOB_BUSY' } if @provider_job

        helper_action = action == 'provider_test' ? 'test' : 'sync'
        payload = { 'action' => helper_action, 'allow_network' => true }
        if helper_action == 'test'
          payload['model'] = data['model'].to_s if data.key?('model')
          payload['prompt'] = data['prompt'].to_s[0, 200] if data.key?('prompt')
        end
        job = { action: action, result: nil, done: false }
        @provider_job = job
        @provider_job_mutex ||= Mutex.new
        Thread.new do
          result = run_provider_helper(payload)
          @provider_job_mutex.synchronize do
            job[:result] = result
            job[:done] = true
          end
        rescue StandardError => e
          @provider_job_mutex.synchronize do
            job[:result] = { 'status' => 'error', 'error' => 'PROVIDER_HELPER_FAILED', 'detail' => e.class.name }
            job[:done] = true
          end
        end
        { status: 'ok', action: "#{action}_started", data: { state: 'RUNNING', implementation_state: 'REAL' } }
      rescue StandardError => e
        @provider_job = nil
        { status: 'error', action: action, error: "PROVIDER_JOB_START_FAILED: #{e.class}: #{e.message}" }
      end

      def process_provider_job
        job = @provider_job
        return unless job

        done = @provider_job_mutex && @provider_job_mutex.synchronize { job[:done] }
        return unless done

        result = @provider_job_mutex.synchronize { job[:result] }
        @provider_job = nil
        send_to_ui('aiDgReceive', { status: result_status(result) == 'ok' ? 'ok' : 'blocked', action: job[:action], data: result })
      rescue StandardError => e
        @provider_job = nil
        send_to_ui('aiDgReceive', { status: 'error', action: job && job[:action], error: "PROVIDER_JOB_FAILED: #{e.class}: #{e.message}" })
      end

      def start_provider_chat_thread(job)
        @provider_job_mutex ||= Mutex.new
        Thread.new do
          result = run_provider_helper('action' => 'agent_ask', 'prompt' => job[:provider_prompt] || job[:prompt], 'allow_network' => true)
          @provider_job_mutex.synchronize do
            job[:result] = result
            job[:provider_done] = true
          end
        rescue StandardError => e
          @provider_job_mutex.synchronize do
            job[:result] = { 'status' => 'error', 'error' => 'PROVIDER_HELPER_FAILED', 'detail' => e.class.name }
            job[:provider_done] = true
          end
        end
      end

      def start_codex_cli_thread(job)
        @provider_job_mutex ||= Mutex.new
        Thread.new do
          result = run_provider_helper('action' => 'codex_ask', 'prompt' => job[:provider_prompt] || job[:prompt], 'allow_network' => true)
          @provider_job_mutex.synchronize do
            job[:result] = result
            job[:provider_done] = true
          end
        rescue StandardError => e
          @provider_job_mutex.synchronize do
            job[:result] = { 'status' => 'error', 'error' => 'CODEX_CLI_HELPER_FAILED', 'detail' => e.class.name }
            job[:provider_done] = true
          end
        end
      end

      def run_provider_helper(payload)
        script = 'E:/AI-DG/mcp_server/provider_cli.py'
        raise LoadError, 'PROVIDER_HELPER_NOT_FOUND' unless File.file?(script)

        configured = ENV['AI_DG_PYTHON'].to_s.strip
        candidates = [
          configured,
          'C:/Users/Admin/AppData/Local/Programs/Python/Python312/python.exe',
          'E:/AI-DG/OUTPUT/runtime/python.exe',
          'C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
          'C:/Windows/py.exe',
          'py.exe'
        ].reject(&:empty?)
        executable = candidates.find { |candidate| candidate.include?(':') ? File.file?(candidate) : true }
        raise LoadError, 'PYTHON_RUNTIME_NOT_FOUND' unless executable

        args = [executable]
        # The MCP/provider code requires Python >= 3.10.  A generic `py -3`
        # can select Python 3.9 on this host and fail while importing server.py.
        args << '-3.12' if File.basename(executable).downcase == 'py.exe'
        args << script
        env = {
          'PYTHONPATH' => ['E:/AI-DG/OUTPUT/mcp_deps', 'E:/AI-DG/OUTPUT/pipeline_deps', 'E:/AI-DG', 'E:/AI-DG/mcp_server'].join(File::PATH_SEPARATOR)
        }
        stdout, stderr, status = Open3.capture3(env, *args, stdin_data: JSON.generate(payload), binmode: true)
        raw = stdout.to_s.sub("\uFEFF", '').strip
        parsed = begin
          JSON.parse(raw)
        rescue JSON::ParserError
          # Some Python launchers prepend a warning. Accept only a complete
          # JSON object line; never attempt to recover arbitrary output.
          parsed_line = nil
          raw.lines.reverse_each do |line|
            begin
              candidate = JSON.parse(line.strip)
              if candidate.is_a?(Hash)
                parsed_line = candidate
                break
              end
            rescue JSON::ParserError
              next
            end
          end
          parsed_line
        end
        # provider_cli intentionally exits 1 for structured provider errors;
        # preserve that JSON error instead of replacing it with a transport
        # failure. This keeps API_KEY_REQUIRED/MODEL_REQUIRED actionable.
        return parsed if parsed.is_a?(Hash)

        unless status.success?
          return {
            'status' => 'error',
            'error' => 'PROVIDER_HELPER_PROCESS_FAILED',
            'exit_code' => status.exitstatus,
            'runtime' => File.basename(executable.to_s),
            'stdout_bytes' => stdout.to_s.bytesize,
            'stderr_bytes' => stderr.to_s.bytesize
          }
        end

        {
          'status' => 'error',
          'error' => 'PROVIDER_HELPER_INVALID_RESPONSE',
          'detail' => 'JSON object expected from helper',
          'runtime' => File.basename(executable.to_s),
          'stdout_bytes' => stdout.to_s.bytesize,
          'stderr_bytes' => stderr.to_s.bytesize
        }
      rescue JSON::ParserError
        { 'status' => 'error', 'error' => 'PROVIDER_HELPER_INVALID_RESPONSE', 'detail' => 'JSON parse failed' }
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
        package_count = payload['package_count'].to_i
        {
          status: 'ok',
          data: {
            pipeline: 'AI-DG 2D→3D',
            status: payload['status'] || 'DONE',
            gate_status: payload['gate_status'] || 'REVIEW_REQUIRED',
            run_id: payload['run_id'],
            generated_utc: payload['generated_utc'],
            package_count: package_count,
            drawing_count: Array(artifacts.dig('index', 'entries')).length,
            dimension_count: Array(artifacts.dig('dimension_graph', 'nodes')).length,
            material_count: Array(artifacts.dig('material_graph', 'materials')).length,
            review_status: review['status'] || 'OPEN',
            review_items: Array(review['items']).first(100),
            build_operations: Array(plan['operations']).first(100),
            blocked_items: Array(plan['blocked_items']).first(100),
            source_packages: package_count,
            artifact_summary: latest
          }
        }
      rescue StandardError => e
        { status: 'error', error: "PIPELINE_STATUS_READ_FAILED: #{e.class}: #{e.message}" }
      end

      def read_provider_state
        path = 'E:/AI-DG/OUTPUT/runtime/provider-state.json'
        return {} unless File.file?(path)

        value = JSON.parse(File.read(path, encoding: 'UTF-8'))
        return {} unless value.is_a?(Hash)

        value.select { |key, _value| %w[operation status model latency_ms request_count error updated_utc].include?(key.to_s) }
      rescue StandardError
        {}
      end

      def push_runtime
        return unless @dialog

        process_provider_job
        send_to_ui('aiDgReceive', { status: 'ok', data: Bridge.runtime_snapshot })
      rescue StandardError => e
        Bridge.send(:log_exception, 'control center push runtime', e) if Bridge.respond_to?(:log_exception, true)
      end

      def start_runtime_timer
        return if @runtime_timer_id

        @runtime_timer_id = UI.start_timer(1.0, true) { push_runtime }
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
        return unless @dialog

        json = JSON.generate(payload)
        @dialog.execute_script("window.#{function_name}(#{json});")
      end

      def load_skill(skill_id, max_chars = nil)
        return { status: 'error', error: 'INVALID_SKILL_ID' } unless skill_id.match?(/\A[A-Za-z0-9._-]+\z/)

        limit = [[max_chars.to_i.zero? ? 6000 : max_chars.to_i, 500].max, 12_000].min
        path = ['E:/AI-DG/skills', 'E:/AI-DG/.agents/skills'].map { |root| File.join(root, skill_id, 'SKILL.md') }.find { |candidate| File.file?(candidate) }
        return { status: 'error', error: 'SKILL_NOT_FOUND', skill_id: skill_id } unless path

        Bridge.record_event('skill_loaded', { skill: skill_id, status: 'SUCCESS' })
        { status: 'ok', skill_id: skill_id, source: path, content: File.read(path, encoding: 'UTF-8')[0, limit], truncated: File.size(path) > limit }
      rescue StandardError => e
        Bridge.record_event('skill_loaded', { skill: skill_id, status: 'ERROR', error: e.message })
        { status: 'error', error: "#{e.class}: #{e.message}", skill_id: skill_id }
      end

      def set_plugin_enabled(plugin_id, enabled)
        return { status: 'error', error: 'INVALID_PLUGIN_ID' } unless plugin_id.match?(/\A[A-Za-z0-9._-]+\z/)
        return { status: 'error', error: 'CORE_PLUGIN_CANNOT_BE_DISABLED' } if plugin_id == 'ai-dg-core' && !enabled

        known = plugin_id == 'ai-dg-core' || File.file?(File.join('E:/AI-DG/plugins', plugin_id, 'manifest.json'))
        return { status: 'error', error: 'PLUGIN_NOT_FOUND', plugin_id: plugin_id } unless known

        path = 'E:/AI-DG/OUTPUT/runtime/plugin-state.json'
        state = File.file?(path) ? JSON.parse(File.read(path, encoding: 'UTF-8')) : {}
        state[plugin_id] = { 'enabled' => !!enabled }
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, JSON.pretty_generate(state), mode: 'w', encoding: 'UTF-8')
        Bridge.record_event('plugin_changed', { plugin: plugin_id, enabled: !!enabled, status: 'SUCCESS' })
        { status: 'ok', plugin_id: plugin_id, enabled: !!enabled, persistence_path: path }
      rescue StandardError => e
        Bridge.record_event('plugin_changed', { plugin: plugin_id, status: 'ERROR', error: e.message })
        { status: 'error', error: "#{e.class}: #{e.message}", plugin_id: plugin_id }
      end

      def reload_plugin(plugin_id)
        return { status: 'error', error: 'INVALID_PLUGIN_ID' } unless plugin_id.match?(/\A[A-Za-z0-9._-]+\z/)
        known = plugin_id == 'ai-dg-core' || File.file?(File.join('E:/AI-DG/plugins', plugin_id, 'manifest.json'))
        return { status: 'error', error: 'PLUGIN_NOT_FOUND', plugin_id: plugin_id } unless known

        Bridge.record_event('plugin_reload_queued', { plugin: plugin_id, status: 'SUCCESS', policy: 'manual_and_graceful_only' })
        { status: 'ok', plugin_id: plugin_id, reload: 'QUEUED_GRACEFUL', policy: 'manual_and_graceful_only' }
      end

      def open_developer_file(path)
        root = File.expand_path('E:/AI-DG').tr('\\', '/')
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

# frozen_string_literal: true

# AI-DG SketchUp MCP bridge.
# Loading this file only defines the bridge and schedules a delayed boot.
# TCP/client I/O stays off the SketchUp UI thread; SketchUp API calls are
# dispatched only by the UI timer through the command queue.

require 'socket'
require 'json'
require 'thread'
require 'fileutils'
require 'time'
require 'digest'
require 'uri'
require 'securerandom'
require_relative 'geometry_builder'

module AI_DG
  module Bridge
    HOST = '127.0.0.1' unless const_defined?(:HOST, false)
    PORT = begin
      Integer(ENV.fetch('AI_DG_SKETCHUP_PORT', '0'))
    rescue StandardError
      0
    end unless const_defined?(:PORT, false)
    IO_TIMEOUT = 15.0 unless const_defined?(:IO_TIMEOUT, false)
    MODEL_WRITE_TIMEOUT = 45.0 unless const_defined?(:MODEL_WRITE_TIMEOUT, false)
    MODEL_WRITE_ACTIONS = %w[
      create_primitive_box create_semantic_item create_group create_component
      transform_entity apply_material set_tag undo set_write_mode
    ].freeze unless const_defined?(:MODEL_WRITE_ACTIONS, false)
    START_DELAY = 5.0 unless const_defined?(:START_DELAY, false)
    TICK_INTERVAL = 0.05 unless const_defined?(:TICK_INTERVAL, false)
    MAX_COMMANDS_PER_TICK = 4 unless const_defined?(:MAX_COMMANDS_PER_TICK, false)
    MAX_REQUEST_BYTES = 1_048_576 unless const_defined?(:MAX_REQUEST_BYTES, false)
    DEFAULT_LOG_PATH = 'E:/AI-DG/OUTPUT/logs/runtime.log' unless const_defined?(:DEFAULT_LOG_PATH, false)
    DEFAULT_EVENT_LOG_PATH = 'E:/AI-DG/OUTPUT/logs/bridge.log' unless const_defined?(:DEFAULT_EVENT_LOG_PATH, false)
    INSTANCE_REGISTRY_DIR = 'E:/AI-DG/OUTPUT/runtime/sketchup-instances' unless const_defined?(:INSTANCE_REGISTRY_DIR, false)
    INSTANCE_HEARTBEAT_INTERVAL = 2.0 unless const_defined?(:INSTANCE_HEARTBEAT_INTERVAL, false)
    remove_const(:LOG_FILES) if const_defined?(:LOG_FILES, false)
    LOG_FILES = %w[bridge mcp tools runtime errors].freeze
    TRACE_LIMIT = 200 unless const_defined?(:TRACE_LIMIT, false)
    DEFAULT_ACCESS_MODE = 'read_only' unless const_defined?(:DEFAULT_ACCESS_MODE, false)
    DEVELOPER_MODE = ENV.fetch('AI_DG_DEVELOPER_MODE', '0') == '1' unless const_defined?(:DEVELOPER_MODE, false)

    DEBUG_STAGE = begin
      Integer(ENV.fetch('AI_DG_DEBUG_STAGE', '9'))
    rescue StandardError
      9
    end unless const_defined?(:DEBUG_STAGE, false)

    STAGE_NAMES = {
      0 => 'B0 loader only',
      1 => 'B1 definitions only',
      2 => 'B2 state only',
      3 => 'B3 timer only',
      4 => 'B4 background thread only',
      5 => 'B5 TCP bind only',
      6 => 'B6 accept thread',
      7 => 'B7 queue dispatch without SketchUp API',
      8 => 'B8 minimal SketchUp API',
      9 => 'B9 full bridge'
    }.freeze unless const_defined?(:STAGE_NAMES, false)

    remove_const(:TOOL_CATALOG) if const_defined?(:TOOL_CATALOG, false)
    TOOL_CATALOG = [
      { id: 'sketchup_ping', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_health', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_runtime_state', permission: 'runtime.read', risk: 'LOW' },
      { id: 'sketchup_get_model_summary', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_selection', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_entity', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_semantic_item', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_create_semantic_item', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_get_hierarchy', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_list_components', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_list_materials', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_list_tags', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_list_scenes', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_camera', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_bounds', permission: 'sketchup.read', risk: 'LOW' },
      { id: 'sketchup_get_trace', permission: 'runtime.read', risk: 'LOW' },
      { id: 'sketchup_list_runtime_tools', permission: 'runtime.read', risk: 'LOW' },
      { id: 'sketchup_set_write_mode', permission: 'sketchup.write_mode', risk: 'HIGH' },
      { id: 'sketchup_capture_viewport', permission: 'filesystem.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_box', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_group', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_component', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_cabinet', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_panel', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_partition', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_shelf', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_door', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_drawer', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_countertop', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_create_component_from_spec', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_transform_entity', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_apply_material', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_set_tag', permission: 'sketchup.write', risk: 'MEDIUM' },
      { id: 'sketchup_undo', permission: 'sketchup.write', risk: 'HIGH' },
      { id: 'sketchup_reload_runtime', permission: 'runtime.reload', risk: 'MEDIUM' }
    ].freeze

    class SelectionObserver < Sketchup::SelectionObserver
      def onSelectionBulkChange(selection)
        Bridge.record_event('selection_changed', { count: selection.length, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'selection observer', e)
      end

      def onSelectionCleared(selection)
        Bridge.record_event('selection_changed', { count: selection.length, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'selection observer', e)
      end

      def onSelectionAdded(selection, entity)
        Bridge.record_event('selection_changed', { count: selection.length, entity_id: (entity.persistent_id rescue nil), status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'selection observer', e)
      end

      def onSelectionRemoved(selection, entity)
        Bridge.record_event('selection_changed', { count: selection.length, entity_id: (entity.persistent_id rescue nil), status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'selection observer', e)
      end
    end

    class ModelObserver < Sketchup::ModelObserver
      def onTransactionCommit(model)
        Bridge.record_event('entity_changed', { kind: 'transaction_commit', entities: model.entities.length, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'model observer', e)
      end

      def onTransactionUndo(model)
        Bridge.record_event('entity_changed', { kind: 'transaction_undo', entities: model.entities.length, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'model observer', e)
      end

      def onTransactionRedo(model)
        Bridge.record_event('entity_changed', { kind: 'transaction_redo', entities: model.entities.length, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'model observer', e)
      end

      def onPostSaveModel(model)
        Bridge.record_event('model_saved', { path: model.path.to_s, status: 'SUCCESS' })
      rescue StandardError => e
        Bridge.send(:log_exception, 'model observer', e)
      end
    end

    if defined?(Sketchup::AppObserver)
      class AppObserver < Sketchup::AppObserver
        def onQuit
          Bridge.stop
        end

        def onNewModel(model)
          Bridge.send(:attach_observers, model)
          Bridge.record_event('model_opened', { model_title: (model.title rescue ''), status: 'SUCCESS' })
          Bridge.record_event('active_model_changed', { model_title: (model.title rescue ''), status: 'SUCCESS' })
        rescue StandardError => e
          Bridge.send(:log_exception, 'app new model observer', e)
        end

        def onOpenModel(model)
          Bridge.send(:attach_observers, model)
          Bridge.record_event('model_opened', { model_title: (model.title rescue ''), status: 'SUCCESS' })
          Bridge.record_event('active_model_changed', { model_title: (model.title rescue ''), status: 'SUCCESS' })
        rescue StandardError => e
          Bridge.send(:log_exception, 'app open model observer', e)
        end

        def onActivateModel(model)
          Bridge.send(:attach_observers, model)
          Bridge.record_event('active_model_changed', { model_title: (model.title rescue ''), status: 'SUCCESS' })
        rescue StandardError => e
          Bridge.send(:log_exception, 'app activate model observer', e)
        end

        def onCloseModel(model)
          Bridge.record_event('active_model_changed', { model_title: (model.title rescue ''), status: 'SUCCESS', closed: true })
        rescue StandardError => e
          Bridge.send(:log_exception, 'app close model observer', e)
        end
      end
    end

    if defined?(Sketchup::EntitiesObserver)
      class EntitiesObserver < Sketchup::EntitiesObserver
        def onElementAdded(entities, entity)
          Bridge.record_event('entity_changed', { kind: 'added', entity_id: (entity.persistent_id rescue nil), status: 'SUCCESS' })
        rescue StandardError => e
          Bridge.send(:log_exception, 'entities observer', e)
        end

        def onElementRemoved(entities, entity_id)
          Bridge.record_event('entity_changed', { kind: 'removed', entity_id: entity_id, status: 'SUCCESS' })
        rescue StandardError => e
          Bridge.send(:log_exception, 'entities observer', e)
        end
      end
    end

    class << self
      def dispatch(request)
        request = request || {}
        action = request['action'].to_s
        request_id = request['request_id'] || "req-#{Time.now.to_f}-#{Thread.current.object_id}"
        session_id = request['session_id']
        @last_request_json = JSON.pretty_generate(safe_code_payload(request))
        request_bytes = (JSON.generate(request).bytesize rescue nil)
        started_at = monotonic_time
        started_wall = Time.now.utc.iso8601(3)
        @last_tool = action
        @last_session_id = session_id if session_id
        record_event('tool_started', { request_id: request_id, session_id: session_id, tool: action, status: 'RUNNING', started_at: started_wall, bytes_in: request_bytes, stage: 'RUBY_BRIDGE' })
        validate_target_request!(request)
        return { status: 'ok', stage: stage_name, request_id: request_id } if DEBUG_STAGE == 7
        return { status: 'error', error: 'Action disabled during B8', request_id: request_id } if DEBUG_STAGE == 8 && action != 'ping'

        data = request['data'] || {}
        model = Sketchup.active_model
        result = case action
                 when 'ping'
                   { status: 'ok', sketchup_version: Sketchup.version, model_title: model.title }
                 when 'health', 'get_runtime_state'
                   { status: 'ok', data: runtime_snapshot }
                 when 'eval_ruby'
                   raise SecurityError, 'eval_ruby is Developer Mode only' unless DEVELOPER_MODE

                   { status: 'ok', result: TOPLEVEL_BINDING.eval(data.fetch('code')).inspect }
                 when 'get_model_info'
                   { status: 'ok', data: model_summary(model) }
                 when 'get_selection'
                   { status: 'ok', data: selection_summary(model) }
                 when 'get_entity'
                   { status: 'ok', data: entity_details(model, data) }
                 when 'get_semantic_item'
                   { status: 'ok', data: semantic_item_summary(model, data) }
                 when 'get_hierarchy'
                   { status: 'ok', data: hierarchy_summary(model, data) }
                 when 'list_components'
                   { status: 'ok', data: component_summary(model) }
                 when 'list_materials'
                   { status: 'ok', data: material_summary(model) }
                 when 'list_tags'
                   { status: 'ok', data: tag_summary(model) }
                 when 'list_scenes'
                   { status: 'ok', data: scene_summary(model) }
                 when 'get_camera'
                   { status: 'ok', data: camera_summary(model.active_view) }
                 when 'get_bounds'
                   { status: 'ok', data: bounds_summary(model) }
                 when 'get_trace'
                   { status: 'ok', data: trace_snapshot(data) }
                 when 'get_code_view'
                   { status: 'ok', data: code_view_snapshot }
                 when 'get_logs'
                   { status: 'ok', data: logs_snapshot(data) }
                 when 'list_tools'
                    { status: 'ok', data: tool_catalog_snapshot }
                 when 'set_write_mode'
                   request_access_mode(data)
                  when 'reload_runtime'
                    reload_runtime_source
                  when 'capture_viewport'
                    capture_viewport(model, data)
                 when 'create_primitive_box'
                   create_primitive_box(model, data)
                 when 'create_semantic_item'
                   create_semantic_item(model, data)
                 when 'create_group'
                   create_group(model, data)
                 when 'create_component'
                   create_component(model, data)
                 when 'transform_entity'
                   transform_entity(model, data)
                 when 'apply_material'
                   apply_material(model, data)
                 when 'set_tag'
                   set_tag(model, data)
                 when 'undo'
                   undo_last_operation(model, data)
                 else
                   { status: 'error', error: "Unknown action: #{action}" }
                 end
        elapsed_ms = ((monotonic_time - started_at) * 1000).round(2)
        response = result.merge(request_id: request_id, session_id: session_id, latency_ms: elapsed_ms, target: instance_snapshot)
        response_bytes = (JSON.generate(response).bytesize rescue nil)
        record_event('tool_finished', { request_id: request_id, session_id: session_id, tool: action, status: response[:status] == 'ok' ? 'SUCCESS' : 'ERROR', started_at: started_wall, ended_at: Time.now.utc.iso8601(3), duration_ms: elapsed_ms, latency_ms: elapsed_ms, bytes_in: request_bytes, bytes_out: response_bytes, retries: 0, stage: 'RUBY_BRIDGE' })
        @last_response_json = JSON.pretty_generate(safe_code_payload(response))
        response
      rescue StandardError => e
        log_exception('dispatch', e)
        elapsed_ms = ((monotonic_time - started_at) * 1000).round(2)
        record_event('tool_finished', { request_id: request_id, session_id: session_id, tool: action, status: 'ERROR', started_at: started_wall, ended_at: Time.now.utc.iso8601(3), duration_ms: elapsed_ms, latency_ms: elapsed_ms, bytes_in: request_bytes, retries: 0, stage: 'RUBY_BRIDGE', error: e.message })
        response = { status: 'error', error: "#{e.class}: #{e.message}", request_id: request_id, latency_ms: ((monotonic_time - started_at) * 1000).round(2), target: (instance_snapshot rescue nil) }
        @last_response_json = JSON.pretty_generate(safe_code_payload(response))
        response
      end

      def schedule_start(delay = START_DELAY)
        return true if runtime_active? || @startup_timer_id || @partial_started
        if DEBUG_STAGE <= 1
          log("#{stage_name}: no runtime scheduled")
          return true
        end

        @startup_timer_id = UI.start_timer(delay, false) do
          @startup_timer_id = nil
          begin
            start
          rescue StandardError => e
            log_exception('delayed start', e)
            cleanup_start_failure
          end
        end
        log("#{stage_name}: boot scheduled in #{delay}s")
        true
      rescue StandardError => e
        @startup_timer_id = nil
        log_exception('schedule_start', e)
        false
      end

      def start
        return true if runtime_active? || @partial_started
        @start_in_progress = true
        initialize_state
        log("#{stage_name}: start begin")

        return partial_start(2, 'state initialized') if DEBUG_STAGE == 2
        attach_app_observer
        attach_observers(Sketchup.active_model)
        create_dispatch_timer
        return partial_start(3, 'UI timer created') if DEBUG_STAGE == 3
        start_idle_worker
        return partial_start(4, 'background worker created') if DEBUG_STAGE == 4
        bind_server
        start_instance_registry
        return partial_start(5, 'TCPServer bound') if DEBUG_STAGE == 5

        @running = true
        start_accept_thread
        return partial_start(6, 'accept thread created') if DEBUG_STAGE == 6

        @runtime_started = true
        @runtime_started_at = Time.now
        record_event('bridge_started', { status: 'SUCCESS', instance_id: instance_id, port: bridge_port })
        log("#{stage_name}: listening on #{HOST}:#{bridge_port} as #{instance_id}")
        true
      rescue StandardError => e
        log_exception('start', e)
        cleanup_start_failure
        false
      ensure
        @start_in_progress = false
      end

      def stop
        record_event('bridge_stopping', { status: 'SUCCESS' })
        @running = false
        detach_observers
        stop_dispatch_timer
        stop_idle_worker
        @startup_timer_id = nil
        stop_instance_registry
        close_server_socket
        close_client_sockets
        detach_app_observer
        thread = @server_thread
        @server_thread = nil
        thread.join(0.5) if thread && thread != Thread.current && thread.alive?
        @runtime_started = false
        @runtime_started_at = nil
        @partial_started = false
        @command_queue = nil
        @result_queue_count = 0
        log('stopped')
        true
      rescue StandardError => e
        log_exception('stop', e)
        false
      end

      def running?
        !!runtime_active?
      end

      def access_mode
        @access_mode ||= DEFAULT_ACCESS_MODE
      end

      def set_access_mode(mode)
        normalized = mode.to_s == 'write_enabled' ? 'write_enabled' : DEFAULT_ACCESS_MODE
        @access_mode = normalized
        record_event('mode_changed', { mode: normalized, status: 'SUCCESS' })
        publish_instance_heartbeat
        normalized
      end

      def request_access_mode(data)
        requested = data['mode'].to_s
        raise ArgumentError, 'INVALID_WRITE_MODE' unless %w[read_only write_enabled].include?(requested)

        if requested == 'write_enabled'
          raise ArgumentError, 'WRITE_MODE_CONFIRMATION_REQUIRED' unless data['confirm'] == true

          approved = UI.messagebox(
            'Cho phép MCP thay đổi model trong tiến trình SketchUp này? Mỗi thao tác ghi vẫn yêu cầu xác nhận riêng.',
            MB_YESNO
          )
          raise RuntimeError, 'USER_DECLINED_WRITE_MODE' unless approved == IDYES
        end
        { status: 'ok', access_mode: set_access_mode(requested) }
      end

      def instance_id
        initialize_instance_identity
        @instance_id
      end

      def bridge_port
        @bound_port || begin
          @server_socket.addr[1] if @server_socket && !@server_socket.closed?
        rescue StandardError
          nil
        end
      end

      def instance_snapshot
        initialize_instance_identity
        model = Sketchup.active_model
        now = Time.now.utc
        {
          instance_id: @instance_id,
          pid: Process.pid,
          boot_id: @boot_id,
          host: HOST,
          port: bridge_port,
          sketchup_version: Sketchup.version,
          model_title: model&.title.to_s,
          model_path: model&.path.to_s,
          bridge_generation: (@reload_generation || 0),
          write_mode: access_mode,
          last_seen: now.iso8601(3),
          last_seen_epoch: now.to_f
        }
      end

      def runtime_snapshot
        model = Sketchup.active_model
        now = Time.now
        trace = trace_snapshot({ 'limit' => 40 })
        {
          sketchup_pid: Process.pid,
          sketchup_version: Sketchup.version,
          instance_id: instance_id,
          boot_id: @boot_id,
          bridge_host: HOST,
          bridge_port: bridge_port,
          model_title: model&.title.to_s,
          model_path: model&.path.to_s,
          bridge_status: runtime_active? ? 'ONLINE' : 'STARTING',
          access_mode: access_mode,
          developer_mode: DEVELOPER_MODE,
           bridge_source: __FILE__,
           bridge_source_sha256: source_sha256,
           reload_generation: (@reload_generation || 0),
           active_tool: active_trace_tool,
           last_latency_ms: last_latency_ms,
           session_id: @last_session_id,
          command_queue: @command_queue ? @command_queue.length : 0,
           result_queue: (@queue_mutex ? @queue_mutex.synchronize { @result_queue_count.to_i } : @result_queue_count.to_i),
          uptime_seconds: @runtime_started_at ? (now - @runtime_started_at).round(1) : 0,
          last_request_at: @last_request_at,
          last_error: @last_error,
          health: {
            bridge: runtime_active? ? 'ONLINE' : 'STARTING',
            mcp: mcp_status
          },
          errors: trace.select { |row| row[:status] == 'ERROR' },
          warnings: [],
          trace: trace
        }
      rescue StandardError => e
        { bridge_status: 'ERROR', access_mode: access_mode, health: { bridge: 'ERROR' }, errors: [{ error: "#{e.class}: #{e.message}" }] }
      end

      def record_event(event, data = {})
        row = {
          event: event.to_s,
          timestamp: Time.now.utc.iso8601(3),
          status: (data[:status] || data['status'] || 'SUCCESS').to_s
        }.merge(data.transform_keys(&:to_sym))
        @trace_mutex ||= Mutex.new
        @trace_mutex.synchronize do
          @trace ||= []
          @trace << row
          @trace.shift while @trace.length > TRACE_LIMIT
        end
        @last_request_at = row[:timestamp] if event.to_s == 'tool_finished'
        append_event_log(row)
        row
      rescue StandardError
        row
      end

      def trace_snapshot(data = {})
        refresh_stale_trace!
        limit = [[data['limit'] || data[:limit] || 100, 1].max.to_i, TRACE_LIMIT].min
        @trace_mutex ||= Mutex.new
        @trace_mutex.synchronize { Array(@trace).last(limit) }
      end

      def refresh_stale_trace!
        cutoff = Time.now - IO_TIMEOUT
        @trace_mutex ||= Mutex.new
        @trace_mutex.synchronize do
          rows = Array(@trace)
          rows.each do |row|
            reconcile_finished_lifecycle!(row, rows)
            next unless row[:status].to_s == 'RUNNING'

            timestamp = begin
              Time.iso8601(row[:timestamp].to_s)
            rescue StandardError
              nil
            end
            next unless timestamp && timestamp < cutoff

            row[:status] = 'TIMEOUT'
            row[:error] = 'request exceeded the bridge result timeout'
          end
        end
      end

      # A started row is deliberately retained for auditability, but it must
      # stop looking active as soon as its matching finished row is recorded.
      # Without this reconciliation, the stale-row watchdog eventually marks
      # successful requests as TIMEOUT even though the API call completed.
      def reconcile_finished_lifecycle!(row, rows)
        event = row[:event].to_s
        finish_event = case event
                       when 'tool_started' then 'tool_finished'
                       when 'skill_started' then 'skill_finished'
                       when 'agent_started' then 'agent_finished'
                       end
        return unless finish_event
        return unless row[:status].to_s == 'RUNNING' || row[:status].to_s == 'TIMEOUT'

        finished = rows.reverse.find do |candidate|
          candidate[:event].to_s == finish_event &&
            candidate[:request_id].to_s == row[:request_id].to_s &&
            candidate[:session_id].to_s == row[:session_id].to_s &&
            (event != 'tool_started' || candidate[:tool].to_s == row[:tool].to_s) &&
            (event == 'tool_started' || candidate[:skill].to_s == row[:skill].to_s)
        end
        return unless finished

        row[:status] = finished[:status]
        row[:ended_at] = finished[:ended_at] || finished[:timestamp]
        if finished[:error]
          row[:error] = finished[:error]
        else
          row.delete(:error)
        end
        row[:latency_ms] = finished[:latency_ms] if finished[:latency_ms]
      end

      def stage_name
        STAGE_NAMES[DEBUG_STAGE] || "B#{DEBUG_STAGE} custom stage"
      end

      def tool_catalog_snapshot
        traces = trace_snapshot({ 'limit' => TRACE_LIMIT })
        catalog = TOOL_CATALOG.reject { |tool| tool[:id].to_s == 'sketchup_eval_ruby' }
        if DEVELOPER_MODE && !catalog.any? { |tool| tool[:id].to_s == 'sketchup_eval_ruby' }
          catalog = catalog + [{ id: 'sketchup_eval_ruby', permission: 'developer.only', risk: 'HIGH' }]
        end
        catalog.map do |tool|
          tool_id = tool[:id].to_s
          related = traces.select do |row|
            action = row[:tool].to_s
            action == tool_id ||
              "sketchup_#{action}" == tool_id ||
              (tool_id == 'sketchup_create_box' && action == 'create_primitive_box')
          end
          started = related.reverse.find { |row| row[:event].to_s == 'tool_started' }
          finished = related.reverse.find { |row| row[:event].to_s == 'tool_finished' }
          tool.merge(
            enabled: true,
            status: finished ? finished[:status].to_s : (started ? started[:status].to_s : 'IDLE'),
            last_run: finished && finished[:timestamp],
            duration_ms: finished && finished[:latency_ms]
          )
        end
      end

      def active_trace_tool
        row = trace_snapshot({ 'limit' => TRACE_LIMIT }).reverse.find { |item| item[:status].to_s == 'RUNNING' }
        row && row[:tool]
      end

      def last_latency_ms
        row = trace_snapshot({ 'limit' => TRACE_LIMIT }).reverse.find { |item| item[:event].to_s == 'tool_finished' }
        row && row[:latency_ms]
      end

      # Reload the currently deployed bridge in-place.  This is deliberately
      # source reload only: it does not stop SketchUp, close the TCP server,
      # touch the model, or bypass the normal-mode eval lock.  The existing
      # runtime state and queues stay intact, while newly defined methods are
      # available to subsequent requests.  This closes the common Extension
      # Manager gap where disable/enable does not unload Ruby in-process.
      def reload_runtime_source
        source = File.expand_path(__FILE__)
        raise LoadError, "Bridge source missing: #{source}" unless File.file?(source)

        geometry_source = File.join(File.dirname(source), 'geometry_builder.rb')
        raise LoadError, "Geometry helper missing: #{geometry_source}" unless File.file?(geometry_source)
        load geometry_source
        load source
        attach_app_observer
        attach_observers(Sketchup.active_model)
        start_instance_registry if runtime_active? && !@instance_registry_started
        @reload_generation = (@reload_generation || 0) + 1
        publish_instance_heartbeat
        @runtime_started_at ||= Time.now
        record_event('runtime_reloaded', {
          status: 'SUCCESS',
          source: source,
          source_sha256: source_sha256,
          geometry_source: geometry_source,
          geometry_source_sha256: Digest::SHA256.file(geometry_source).hexdigest,
          reload_generation: @reload_generation
        })
        { status: 'ok', reloaded: true, source: source, source_sha256: source_sha256, geometry_source: geometry_source, geometry_source_sha256: Digest::SHA256.file(geometry_source).hexdigest, reload_generation: @reload_generation }
      rescue StandardError => e
        record_event('runtime_reloaded', { status: 'ERROR', error: e.message })
        raise
      end

      def source_sha256
        Digest::SHA256.file(File.expand_path(__FILE__)).hexdigest
      rescue StandardError
        nil
      end

      def code_view_snapshot
        source_files = [
          ['Ruby bridge dispatch', File.expand_path(__FILE__), 180, 120],
          ['Python MCP handlers', 'E:/AI-DG/mcp_server/server.py', 130, 120]
        ].map do |label, path, start_line, line_count|
          {
            label: label,
            path: path,
            start_line: start_line,
            exists: File.file?(path),
            excerpt: File.file?(path) ? File.readlines(path, encoding: 'UTF-8', invalid: :replace, undef: :replace, replace: '')[start_line - 1, line_count].to_a.join : ''
          }
        rescue StandardError => e
          { label: label, path: path, start_line: start_line, exists: false, excerpt: "#{e.class}: #{e.message}" }
        end
        {
          last_mcp_request_json: (@last_request_json || '{}'),
          last_mcp_response_json: (@last_response_json || '{}'),
          runtime_errors: trace_snapshot({ 'limit' => TRACE_LIMIT }).select { |row| %w[ERROR TIMEOUT BLOCKED].include?(row[:status].to_s) },
          source_files: source_files
        }
      end

      def logs_snapshot(data = {})
        limit = [[(data['limit'] || data[:limit] || 80).to_i, 1].max, 200].min
        files = LOG_FILES.each_with_object({}) do |name, output|
          path = File.join('E:/AI-DG/OUTPUT/logs', "#{name}.log")
          lines = File.file?(path) ? File.readlines(path, encoding: 'UTF-8', invalid: :replace, undef: :replace, replace: '').last(limit) : []
          output["#{name}.log"] = {
            path: path,
            exists: File.file?(path),
            lines: lines.map { |line| line.gsub(/(api[_-]?key|authorization|bearer|secret|password)\s*[:=]\s*[^\s,}]+/i, '\\1=[REDACTED]') }
          }
        rescue StandardError => e
          output["#{name}.log"] = { path: path, exists: false, lines: ["#{e.class}: #{e.message}"] }
        end
        { root: 'E:/AI-DG/OUTPUT/logs', limit: limit, files: files }
      end

      def safe_code_payload(value, key = nil, depth = 0)
        return '[TRUNCATED]' if depth > 8
        return '[REDACTED]' if key.to_s.match?(/api[_-]?key|secret|password|token|authorization|prompt|content|code/i)

        case value
        when Hash
          value.each_with_object({}) do |(child_key, child_value), output|
            output[child_key.to_s] = safe_code_payload(child_value, child_key, depth + 1)
          end
        when Array
          value.first(200).map { |child| safe_code_payload(child, key, depth + 1) }
        when String
          value.length > 4000 ? "#{value[0, 4000]}…" : value
        else
          value
        end
      end

      private

      def model_summary(model)
        bounds = model.bounds
        {
          title: model.title,
          path: model.path,
          entities: model.entities.length,
          definitions: model.definitions.length,
          materials: model.materials.length,
          tags: model.layers.length,
          scenes: model.pages.length,
          selection: model.selection.length,
          bounds_mm: [bounds.width.to_mm.round(3), bounds.depth.to_mm.round(3), bounds.height.to_mm.round(3)]
        }
      end

      def bounds_summary(model)
        bounds = model.bounds
        {
          min_mm: [bounds.min.x.to_mm.round(3), bounds.min.y.to_mm.round(3), bounds.min.z.to_mm.round(3)],
          max_mm: [bounds.max.x.to_mm.round(3), bounds.max.y.to_mm.round(3), bounds.max.z.to_mm.round(3)],
          size_mm: [bounds.width.to_mm.round(3), bounds.depth.to_mm.round(3), bounds.height.to_mm.round(3)]
        }
      end

      def camera_summary(view)
        camera = view.camera
        {
          view_class: view.class.name,
          perspective: camera.perspective?,
          eye: camera.eye.to_a,
          target: camera.target.to_a,
          up: camera.up.to_a,
          fov: (camera.fov rescue nil),
          aspect_ratio: (camera.aspect_ratio rescue nil)
        }
      end

      def selection_summary(model)
        {
          count: model.selection.length,
          items: model.selection.to_a.first(50).map { |entity| entity_summary(entity) }
        }
      end

      def entity_details(model, data)
        persistent_id = Integer(data['persistent_id'] || data[:persistent_id])
        entity = model.find_entity_by_persistent_id(persistent_id) if model.respond_to?(:find_entity_by_persistent_id)
        entity ||= find_entity_recursive(model.entities, persistent_id)
        return { found: false, persistent_id: persistent_id, error: 'ENTITY_NOT_FOUND' } unless entity && entity.valid?

        entity_summary(entity).merge(found: true, attributes: attribute_summary(entity))
      rescue ArgumentError, TypeError
        { found: false, error: 'INVALID_ARGUMENT: persistent_id must be an integer' }
      end

      def semantic_item_summary(model, data)
        item_code = data['item_code'].to_s.strip
        return { found: false, error: 'SEMANTIC_ITEM_CODE_REQUIRED' } if item_code.empty?

        root = model.entities.to_a.find do |entity|
          entity.respond_to?(:get_attribute) && entity.get_attribute('AI_DG', 'item_code').to_s == item_code && entity.valid?
        end
        return { found: false, item_code: item_code, error: 'SEMANTIC_ITEM_NOT_FOUND' } unless root

        parts = if root.respond_to?(:entities)
                   root.entities.to_a.first(500).map do |child|
                     entity_summary(child).merge(attributes: attribute_summary(child))
                   end
                 else
                   []
                 end
        {
          found: true,
          item_code: item_code,
          root: entity_summary(root).merge(attributes: attribute_summary(root)),
          parts: parts,
          part_count: parts.length,
          readback_source: 'official_sketchup_ruby_api'
        }
      rescue StandardError => e
        { found: false, item_code: item_code, error: "SEMANTIC_ITEM_READ_FAILED: #{e.class}: #{e.message}" }
      end

      def find_entity_recursive(entities, persistent_id, deadline = monotonic_time + 2.0)
        stack = entities.to_a.reverse
        visited = 0
        until stack.empty? || monotonic_time >= deadline || visited >= 10_000
          entity = stack.pop
          visited += 1
          return entity if entity.respond_to?(:persistent_id) && entity.persistent_id == persistent_id
          next unless container_entity?(entity)

          entity.entities.to_a.reverse_each { |child| stack << child }
        end
        nil
      end

      def entity_summary(entity)
        bounds = entity.bounds
        result = {
          type: entity.class.name.split('::').last,
          persistent_id: (entity.persistent_id rescue nil),
          name: (entity.name.to_s rescue ''),
          layer: (entity.layer&.name.to_s rescue ''),
          visible: (entity.visible? rescue true),
          bounds_mm: [bounds.width.to_mm.round(3), bounds.depth.to_mm.round(3), bounds.height.to_mm.round(3)]
        }
        result[:min_mm] = [bounds.min.x.to_mm.round(3), bounds.min.y.to_mm.round(3), bounds.min.z.to_mm.round(3)]
        result[:max_mm] = [bounds.max.x.to_mm.round(3), bounds.max.y.to_mm.round(3), bounds.max.z.to_mm.round(3)]
        result[:transformation] = entity.transformation.to_a.map { |value| value.round(8) } if entity.respond_to?(:transformation)
        if entity.respond_to?(:definition)
          definition = entity.definition
          result[:definition] = definition.name.to_s
          result[:definition_guid] = (definition.guid rescue nil)
        end
        if entity.respond_to?(:entities)
          result[:children] = entity.entities.length
          result[:faces] = entity.entities.grep(Sketchup::Face).length
          result[:edges] = entity.entities.grep(Sketchup::Edge).length
        end
        result
      rescue StandardError => e
        { type: entity.class.name, error: "#{e.class}: #{e.message}" }
      end

      def attribute_summary(entity)
        dictionaries = entity.attribute_dictionaries
        return {} unless dictionaries

        dictionaries.each_with_object({}) do |dictionary, output|
          keys = dictionary.keys.first(100)
          output[dictionary.name.to_s] = keys.each_with_object({}) { |key, values| values[key.to_s] = dictionary[key] }
        end
      rescue StandardError
        {}
      end

      def hierarchy_summary(model, data)
        max_depth = [[(data['max_depth'] || 3).to_i, 0].max, 8].min
        max_items = [[(data['max_items'] || 200).to_i, 1].max, 1000].min
        deadline = monotonic_time + 2.0
        count = 0
        stack = model.entities.to_a.reverse.map { |entity| [entity, 0] }
        items = []
        truncated_reason = nil
        until stack.empty?
          break if count >= max_items
          if monotonic_time >= deadline
            truncated_reason = 'TIME_LIMIT'
            break
          end

          entity, depth = stack.pop
          count += 1
          items << entity_summary(entity).merge(depth: depth)
          next unless depth < max_depth && container_entity?(entity)

          entity.entities.to_a.reverse_each { |child| stack << [child, depth + 1] }
        end
        truncated_reason ||= 'MAX_ITEMS' if count >= max_items && !stack.empty?
        {
          max_depth: max_depth,
          max_items: max_items,
          returned: count,
          truncated: !stack.empty?,
          truncated_reason: truncated_reason,
          items: items
        }
      end

      def container_entity?(entity)
        entity.is_a?(Sketchup::Group) || entity.is_a?(Sketchup::ComponentInstance)
      end

      def component_summary(model)
        rows = model.definitions.to_a.first(500).map do |definition|
          {
            name: definition.name.to_s,
            guid: (definition.guid rescue nil),
            instances: (definition.instances.length rescue 0),
            entities: (definition.entities.length rescue 0),
            bounds_mm: begin
              bounds = definition.bounds
              [bounds.width.to_mm.round(3), bounds.depth.to_mm.round(3), bounds.height.to_mm.round(3)]
            rescue StandardError
              nil
            end
          }
        end
        { count: rows.length, items: rows.first(500) }
      end

      def material_summary(model)
        rows = model.materials.to_a.first(500).map do |material|
          {
            name: material.name.to_s,
            color: (material.color.to_a rescue nil),
            alpha: (material.alpha rescue nil),
            texture: (material.texture&.filename rescue nil)
          }
        end
        { count: rows.length, items: rows.first(500) }
      end

      def tag_summary(model)
        rows = model.layers.to_a.first(500).map do |layer|
          { name: layer.name.to_s, visible: (layer.visible? rescue true), page_behavior: (layer.page_behavior rescue nil) }
        end
        { count: rows.length, items: rows.first(500) }
      end

      def scene_summary(model)
        rows = model.pages.to_a.first(500).map do |page|
          { name: page.name.to_s, persistent_id: (page.persistent_id rescue nil), description: (page.description.to_s rescue '') }
        end
        { count: rows.length, items: rows.first(500) }
      end

      def capture_viewport(model, data)
        path = File.expand_path(data.fetch('path'))
        guard_filesystem_write!(path)
        FileUtils.mkdir_p(File.dirname(path))
        view = model.active_view
        original_camera = view.camera
        begin
          view.zoom_extents
          view.write_image(path)
        ensure
          view.camera = original_camera if original_camera
          view.show if view.respond_to?(:show)
        end
        { status: 'ok', image_path: path, view_mode: data['view_mode'] || 'current' }
      end

      def guard_filesystem_write!(path)
        normalized = path.to_s.tr('\\', '/').upcase
        normalized = normalized.sub(%r{\A//\?/}, '').sub(%r{\A/\?/}, '')
        raise SecurityError, 'SKETCHUP_SYSTEM_FILE_WRITE_DENIED' if normalized.end_with?('/TOOLS/SKETCHUP.RB') && normalized.include?('/SKETCHUP/')
        raise SecurityError, 'PROTECTED_DRIVE_WRITE_DENIED' if normalized.match?(/\AD:\//)
        raise SecurityError, 'SKETCHUP_FILE_WRITE_DENIED' if %w[.SKP .SKB].include?(File.extname(normalized))
      end

      def v2_scoped_preapproval?(data)
        data.is_a?(Hash) &&
          data['approval_mode'] == 'user_preapproved_v2' &&
          data['tool_name'] == 'ai_dg_execute_build_ir_v2' &&
          data['confirm_write'] == true &&
          data['schema_version'].to_i == 2 &&
          data['pipeline_stage'] == '2D3D-V2'
      end

      def guard_model_write!(data = nil)
        raise RuntimeError, 'READ_ONLY_MODE: enable write mode through MCP first' unless access_mode == 'write_enabled'
        if v2_scoped_preapproval?(data)
          record_event('model_write_preapproved', {
            tool: data['tool_name'],
            item_code: data['item_code'],
            approval_mode: data['approval_mode'],
            status: 'SUCCESS'
          })
          return true
        end
        approved = UI.messagebox('AI-DG yêu cầu thay đổi model hiện tại. Cho phép thao tác này?', MB_YESNO)
        raise RuntimeError, 'USER_DECLINED_MODEL_WRITE' unless approved == IDYES
        raise RuntimeError, 'WRITE_APPROVAL_EXPIRED' if @active_request_deadline && monotonic_time >= @active_request_deadline
        true
      end

      def create_primitive_box(model, data)
        guard_model_write!
        origin = data['origin'] || [0, 0, 0]
        dimensions = %w[width_mm depth_mm height_mm].map { |key| Float(data.fetch(key)) }
        raise ArgumentError, 'WRITE_DIMENSIONS_INVALID' unless dimensions.all? { |value| value.finite? && value.positive? && value <= 100_000 }
        raise ArgumentError, 'WRITE_ORIGIN_INVALID' unless origin.is_a?(Array) && origin.length == 3 && origin.all? { |value| Float(value).finite? }
        origin = origin.map(&:to_f)
        operation_started = false
        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        before = model_summary(model)
        target = { type: 'Sketchup::Group', name: data['name'] || 'AI_DG_BOX', dimensions_mm: dimensions, origin: origin }
        record_event('model_write_started', { operation_id: operation_id, tool: 'sketchup_create_box', target: target, status: 'RUNNING', before: before })
        model.start_operation('AI-DG Create Box', true)
        operation_started = true
        group = AI_DG::Geometry.create_box(
          model.active_entities,
          data.fetch('width_mm').to_f,
          data.fetch('depth_mm').to_f,
          data.fetch('height_mm').to_f,
          origin
        )
        group.name = data['name'] || 'AI_DG_BOX'
        AI_DG::Geometry.attach_meta(group, {
          operation_id: operation_id,
          tool: 'sketchup_create_box',
          created_utc: Time.now.utc.iso8601,
          access_mode: access_mode
        })
        measured = [group.bounds.width.to_mm, group.bounds.depth.to_mm, group.bounds.height.to_mm]
        verified = group.valid? && group.is_a?(Sketchup::Group) && group.entities.grep(Sketchup::Face).length >= 6 &&
                   measured.zip(dimensions).all? { |actual, expected| (actual - expected).abs <= 0.1 } &&
                   model.entities.length == before[:entities].to_i + 1
        raise RuntimeError, 'WRITE_VERIFY_FAILED' unless verified
        model.commit_operation
        operation_started = false
        after = model_summary(model)
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_box', target: target, status: 'SUCCESS', verified: true, after: after })
        { status: 'ok', name: group.name, operation_id: operation_id, before: before, after: after, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_box', target: (target rescue nil), status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def create_semantic_item(model, data)
        guard_model_write!(data)
        item_code = data['item_code'].to_s.strip
        raise ArgumentError, 'SEMANTIC_ITEM_CODE_REQUIRED' if item_code.empty?
        tool_name = data['tool_name'].to_s.strip
        tool_name = 'sketchup_create_semantic_item' if tool_name.empty?
        builder_type = data['builder_type'].to_s.strip
        builder_type = 'component_from_spec' if builder_type.empty?

        parts = data['parts']
        raise ArgumentError, 'SEMANTIC_PARTS_REQUIRED' unless parts.is_a?(Array) && !parts.empty? && parts.length <= 500

        normalized_parts = parts.each_with_index.map do |part, index|
          raise ArgumentError, 'SEMANTIC_PART_INVALID' unless part.is_a?(Hash)

          dimensions = %w[width_mm depth_mm height_mm].map { |key| Float(part.fetch('dimensions_mm').fetch(key)) }
          raise ArgumentError, 'SEMANTIC_PART_DIMENSIONS_INVALID' unless dimensions.all? { |value| value.finite? && value.positive? && value <= 100_000 }

          origin = part['origin_mm'] || [0, 0, 0]
          raise ArgumentError, 'SEMANTIC_PART_ORIGIN_INVALID' unless origin.is_a?(Array) && origin.length == 3 && origin.all? { |value| Float(value).finite? }

          {
            index: index,
            part_id: part['part_id'].to_s.strip.empty? ? "PART-#{index + 1}" : part['part_id'].to_s.strip,
            region_id: part['region_id'].to_s.strip,
            role: part['role'].to_s.strip.empty? ? 'unspecified' : part['role'].to_s.strip,
            visibility: part['visibility'].to_s.strip.empty? ? 'VISIBLE' : part['visibility'].to_s.strip,
            material_code: part['material_code'].to_s.strip,
            dimensions: dimensions,
            origin: origin.map(&:to_f)
          }
        end

        operation_started = false
        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        before = model_summary(model)
        target = { type: 'semantic_item', item_code: item_code, builder_type: builder_type, part_count: normalized_parts.length }
        record_event('model_write_started', { operation_id: operation_id, tool: tool_name, target: target, status: 'RUNNING', before: before })
        model.start_operation('AI-DG Create Semantic Item', true)
        operation_started = true
        root = model.active_entities.add_group
        root.name = data['name'].to_s.strip.empty? ? "AI_DG_ITEM_#{item_code}" : data['name'].to_s.strip
        AI_DG::Geometry.attach_meta(root, {
          operation_id: operation_id,
          tool: tool_name,
          builder_type: builder_type,
          schema_version: data['schema_version'] || '0.1',
          item_code: item_code,
          pipeline_stage: data['pipeline_stage'] || 'M6-BUILD',
          source_refs: Array(data['source_refs']).first(100).map(&:to_s),
          created_utc: Time.now.utc.iso8601
        })

        created_parts = normalized_parts.map do |part|
          material = nil
          unless part[:material_code].empty?
            material = AI_DG::Geometry.get_or_create_material(model, part[:material_code])
          end
          child = AI_DG::Geometry.create_box(root.entities, *part[:dimensions], part[:origin], material, {
            operation_id: operation_id,
            item_code: item_code,
            part_id: part[:part_id],
            region_id: part[:region_id],
            role: part[:role],
            visibility: part[:visibility],
            material_code: part[:material_code],
            builder_type: builder_type
          })
          child.name = "#{item_code}_#{part[:role]}_#{part[:part_id]}"
          {
            part_id: part[:part_id],
            role: part[:role],
            persistent_id: (child.persistent_id rescue nil),
            bounds_mm: [child.bounds.width.to_mm.round(3), child.bounds.depth.to_mm.round(3), child.bounds.height.to_mm.round(3)]
          }
        end

        verified = root.valid? && root.entities.grep(Sketchup::Group).length == normalized_parts.length &&
                   created_parts.length == normalized_parts.length
        raise RuntimeError, 'SEMANTIC_BUILD_VERIFY_FAILED' unless verified

        model.commit_operation
        operation_started = false
        after = model_summary(model)
        record_event('model_write_finished', { operation_id: operation_id, tool: tool_name, target: target, status: 'SUCCESS', verified: true, after: after })
        {
          status: 'ok',
          operation_id: operation_id,
          tool: tool_name,
          builder_type: builder_type,
          item_code: item_code,
          root_persistent_id: (root.persistent_id rescue nil),
          parts: created_parts,
          before: before,
          after: after,
          verified: true
        }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: tool_name, target: (target rescue nil), status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def create_group(model, data)
        guard_model_write!
        name = data['name'].to_s.strip
        raise ArgumentError, 'GROUP_NAME_REQUIRED' if name.empty?

        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        operation_started = false
        before = model_summary(model)
        model.start_operation('AI-DG Create Group', true)
        operation_started = true
        group = model.active_entities.add_group
        group.name = name
        AI_DG::Geometry.attach_meta(group, {
          operation_id: operation_id,
          tool: 'sketchup_create_group',
          item_id: data['item_id'].to_s,
          source_spec_id: data['source_spec_id'].to_s,
          build_version: data['build_version'] || '0.1',
          created_utc: Time.now.utc.iso8601
        })
        raise RuntimeError, 'GROUP_VERIFY_FAILED' unless group.valid? && group.name == name

        model.commit_operation
        operation_started = false
        after = model_summary(model)
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_group', status: 'SUCCESS', verified: true, after: after })
        { status: 'ok', tool: 'sketchup_create_group', operation_id: operation_id, persistent_id: (group.persistent_id rescue nil), name: name, before: before, after: after, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_group', status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def create_component(model, data)
        guard_model_write!
        name = data['name'].to_s.strip
        raise ArgumentError, 'COMPONENT_NAME_REQUIRED' if name.empty?
        parts = data['parts']
        raise ArgumentError, 'COMPONENT_PARTS_REQUIRED' unless parts.is_a?(Array) && !parts.empty? && parts.length <= 500

        normalized_parts = parts.each_with_index.map do |part, index|
          raise ArgumentError, 'COMPONENT_PART_INVALID' unless part.is_a?(Hash) && part['dimensions_mm'].is_a?(Hash)

          dimensions = %w[width_mm depth_mm height_mm].map { |key| Float(part['dimensions_mm'].fetch(key)) }
          raise ArgumentError, 'COMPONENT_PART_DIMENSIONS_INVALID' unless dimensions.all? { |value| value.finite? && value.positive? && value <= 100_000 }

          origin = part['origin_mm'] || [0, 0, 0]
          raise ArgumentError, 'COMPONENT_PART_ORIGIN_INVALID' unless origin.is_a?(Array) && origin.length == 3 && origin.all? { |value| Float(value).finite? }

          {
            part_id: part['part_id'].to_s.strip.empty? ? "PART-#{index + 1}" : part['part_id'].to_s.strip,
            role: part['role'].to_s.strip.empty? ? 'unspecified' : part['role'].to_s.strip,
            material_code: part['material_code'].to_s.strip,
            dimensions: dimensions,
            origin: origin.map(&:to_f)
          }
        end

        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        operation_started = false
        before = model_summary(model)
        model.start_operation('AI-DG Create Component', true)
        operation_started = true
        definition = model.definitions.add(name)
        normalized_parts.each do |part|
          material = part[:material_code].empty? ? nil : AI_DG::Geometry.get_or_create_material(model, part[:material_code])
          child = AI_DG::Geometry.create_box(definition.entities, *part[:dimensions], part[:origin], material, {
            operation_id: operation_id,
            part_id: part[:part_id],
            role: part[:role],
            material_code: part[:material_code],
            builder_type: 'create_component'
          })
          child.name = "#{name}_#{part[:role]}_#{part[:part_id]}"
        end
        instance = model.active_entities.add_instance(definition, Geom::Transformation.new)
        instance.name = name
        AI_DG::Geometry.attach_meta(instance, {
          operation_id: operation_id,
          tool: 'sketchup_create_component',
          item_id: data['item_id'].to_s,
          source_spec_id: data['source_spec_id'].to_s,
          build_version: data['build_version'] || '0.1',
          source_refs: Array(data['source_refs']).first(100).map(&:to_s),
          created_utc: Time.now.utc.iso8601
        })
        verified = instance.valid? && definition.entities.length == normalized_parts.length && definition.instances.include?(instance)
        raise RuntimeError, 'COMPONENT_VERIFY_FAILED' unless verified

        model.commit_operation
        operation_started = false
        after = model_summary(model)
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_component', status: 'SUCCESS', verified: true, after: after })
        { status: 'ok', tool: 'sketchup_create_component', operation_id: operation_id, persistent_id: (instance.persistent_id rescue nil), definition: definition.name.to_s, part_count: normalized_parts.length, before: before, after: after, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_create_component', status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def transform_entity(model, data)
        guard_model_write!
        persistent_id = Integer(data['persistent_id'])
        translation = data['translation_mm'] || [0, 0, 0]
        raise ArgumentError, 'TRANSFORM_TRANSLATION_INVALID' unless translation.is_a?(Array) && translation.length == 3 && translation.all? { |value| Float(value).finite? }
        entity = model.find_entity_by_persistent_id(persistent_id) if model.respond_to?(:find_entity_by_persistent_id)
        entity ||= find_entity_recursive(model.entities, persistent_id)
        raise ArgumentError, 'ENTITY_NOT_FOUND' unless entity && entity.valid? && entity.respond_to?(:transform!)

        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        operation_started = false
        before = entity_summary(entity)
        model.start_operation('AI-DG Transform Entity', true)
        operation_started = true
        vector = Geom::Vector3d.new(*translation.map { |value| value.to_f.mm })
        entity.transform!(Geom::Transformation.translation(vector))
        raise RuntimeError, 'TRANSFORM_VERIFY_FAILED' unless entity.valid?
        model.commit_operation
        operation_started = false
        after = entity_summary(entity)
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_transform_entity', status: 'SUCCESS', verified: true, before: before, after: after })
        { status: 'ok', tool: 'sketchup_transform_entity', operation_id: operation_id, persistent_id: persistent_id, before: before, after: after, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_transform_entity', status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def apply_material(model, data)
        guard_model_write!
        persistent_id = Integer(data['persistent_id'])
        material_code = data['material_code'].to_s.strip
        raise ArgumentError, 'MATERIAL_CODE_REQUIRED' if material_code.empty?
        entity = model.find_entity_by_persistent_id(persistent_id) if model.respond_to?(:find_entity_by_persistent_id)
        entity ||= find_entity_recursive(model.entities, persistent_id)
        raise ArgumentError, 'ENTITY_NOT_FOUND' unless entity && entity.valid?

        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        operation_started = false
        model.start_operation('AI-DG Apply Material', true)
        operation_started = true
        material = AI_DG::Geometry.get_or_create_material(model, material_code)
        AI_DG::Geometry.paint_entity(entity, material)
        AI_DG::Geometry.attach_meta(entity, { operation_id: operation_id, material_code: material_code, material_role: data['material_role'].to_s })
        raise RuntimeError, 'MATERIAL_VERIFY_FAILED' unless entity.valid? && entity.get_attribute('AI_DG', 'material_code').to_s == material_code
        model.commit_operation
        operation_started = false
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_apply_material', status: 'SUCCESS', verified: true, persistent_id: persistent_id, material_code: material_code })
        { status: 'ok', tool: 'sketchup_apply_material', operation_id: operation_id, persistent_id: persistent_id, material_code: material_code, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_apply_material', status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def set_tag(model, data)
        guard_model_write!
        persistent_id = Integer(data['persistent_id'])
        tag_name = data['tag'].to_s.strip
        raise ArgumentError, 'TAG_REQUIRED' if tag_name.empty?
        entity = model.find_entity_by_persistent_id(persistent_id) if model.respond_to?(:find_entity_by_persistent_id)
        entity ||= find_entity_recursive(model.entities, persistent_id)
        raise ArgumentError, 'ENTITY_NOT_FOUND' unless entity && entity.valid?

        operation_id = "op-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}-#{Thread.current.object_id}"
        operation_started = false
        model.start_operation('AI-DG Set Tag', true)
        operation_started = true
        tag = model.layers[tag_name] || model.layers.add(tag_name)
        entity.layer = tag
        AI_DG::Geometry.attach_meta(entity, { operation_id: operation_id, tag: tag_name })
        raise RuntimeError, 'TAG_VERIFY_FAILED' unless entity.valid? && entity.layer.name.to_s == tag_name
        model.commit_operation
        operation_started = false
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_set_tag', status: 'SUCCESS', verified: true, persistent_id: persistent_id, tag: tag_name })
        { status: 'ok', tool: 'sketchup_set_tag', operation_id: operation_id, persistent_id: persistent_id, tag: tag_name, verified: true }
      rescue StandardError => e
        model.abort_operation if operation_started
        record_event('model_write_finished', { operation_id: operation_id, tool: 'sketchup_set_tag', status: 'ERROR', error: e.message, rollback: operation_started }) if operation_id
        raise
      end

      def undo_last_operation(model, data)
        guard_model_write!
        raise SecurityError, 'UNDO_CONFIRMATION_REQUIRED' unless data['confirm'] == true

        before = model_summary(model)
        result = model.undo
        after = model_summary(model)
        record_event('model_write_finished', { operation_id: "undo-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}", tool: 'sketchup_undo', status: 'SUCCESS', verified: true, before: before, after: after })
        { status: 'ok', tool: 'sketchup_undo', result: result, before: before, after: after, verified: true }
      rescue StandardError => e
        record_event('model_write_finished', { operation_id: "undo-#{Time.now.utc.strftime('%Y%m%dT%H%M%S.%LZ')}", tool: 'sketchup_undo', status: 'ERROR', error: e.message })
        raise
      end

      def initialize_instance_identity
        @boot_id ||= SecureRandom.uuid
        @instance_id ||= "su-#{Process.pid}-#{@boot_id.delete('-')[0, 12]}"
        @instance_registry_path ||= File.join(INSTANCE_REGISTRY_DIR, "#{@instance_id}.json")
      end

      def validate_target_request!(request)
        return true unless request['bridge_transport'] == 'tcp'

        target = request['target']
        raise RuntimeError, 'TARGET_REQUIRED' unless target.is_a?(Hash)

        expected = {
          'instance_id' => instance_id,
          'pid' => Process.pid,
          'boot_id' => @boot_id,
          'port' => bridge_port
        }
        mismatch = expected.any? { |key, value| target[key].to_s != value.to_s }
        raise RuntimeError, 'TARGET_IDENTITY_MISMATCH' if mismatch

        true
      end

      def start_instance_registry
        initialize_instance_identity
        return true if @instance_registry_started

        FileUtils.mkdir_p(INSTANCE_REGISTRY_DIR)
        @instance_registry_queue = Queue.new
        @instance_registry_writer = Thread.new do
          loop do
            message = @instance_registry_queue.pop
            break if message == :stop
            if message == :delete
              File.delete(@instance_registry_path) if File.file?(@instance_registry_path)
            else
              write_instance_registry_file(message)
            end
          rescue StandardError => e
            log_exception('instance registry writer', e)
          end
        end
        @instance_registry_writer.abort_on_exception = false
        @instance_registry_started = true
        @instance_heartbeat_timer_id = UI.start_timer(INSTANCE_HEARTBEAT_INTERVAL, true) { publish_instance_heartbeat }
        publish_instance_heartbeat
        true
      rescue StandardError => e
        @instance_registry_started = false
        log_exception('start instance registry', e)
        false
      end

      def publish_instance_heartbeat
        return false unless @instance_registry_started && bridge_port

        # Only the UI thread reads SketchUp model state. The writer thread owns
        # filesystem I/O, keeping heartbeat writes out of viewport callbacks.
        snapshot = instance_snapshot
        while @instance_registry_queue.length > 1
          @instance_registry_queue.pop(true)
        end
        @instance_registry_queue << snapshot
        true
      rescue ThreadError
        retry
      rescue StandardError => e
        log_exception('publish instance heartbeat', e)
        false
      end

      def write_instance_registry_file(snapshot)
        FileUtils.mkdir_p(INSTANCE_REGISTRY_DIR)
        temp_path = "#{@instance_registry_path}.#{Thread.current.object_id}.tmp"
        File.open(temp_path, 'wb') do |file|
          file.write(JSON.pretty_generate(snapshot))
          file.write("\n")
          file.flush
          file.fsync rescue nil
        end
        begin
          File.rename(temp_path, @instance_registry_path)
        rescue Errno::EACCES, Errno::EEXIST
          File.delete(@instance_registry_path) if File.file?(@instance_registry_path)
          File.rename(temp_path, @instance_registry_path)
        ensure
          File.delete(temp_path) if File.file?(temp_path)
        end
      end

      def stop_instance_registry
        if @instance_heartbeat_timer_id
          UI.stop_timer(@instance_heartbeat_timer_id)
          @instance_heartbeat_timer_id = nil
        end
        queue = @instance_registry_queue
        writer = @instance_registry_writer
        if queue && writer && writer.alive?
          queue << :delete
          queue << :stop
          writer.join(1.0) unless writer == Thread.current
        end
        File.delete(@instance_registry_path) if @instance_registry_path && File.file?(@instance_registry_path)
        @instance_registry_queue = nil
        @instance_registry_writer = nil
        @instance_registry_started = false
        true
      rescue StandardError => e
        log_exception('stop instance registry', e)
        false
      end

      def initialize_state
        initialize_instance_identity
        @command_queue ||= Queue.new
        @queue_mutex ||= Mutex.new
        @result_queue_count ||= 0
        @client_sockets ||= []
        @client_threads ||= []
        @client_mutex ||= Mutex.new
        @mcp_status ||= 'DISCONNECTED'
        @trace ||= []
        @access_mode ||= DEFAULT_ACCESS_MODE
        @last_error = nil unless defined?(@last_error)
      end

      def attach_app_observer
        return unless defined?(Sketchup::AppObserver)
        return if @app_observer_attached

        @app_observer ||= AppObserver.new
        Sketchup.add_observer(@app_observer)
        @app_observer_attached = true
        record_event('app_observer_attached', { status: 'SUCCESS' })
      rescue StandardError => e
        log_exception('attach app observer', e)
      end

      def detach_app_observer
        return unless @app_observer_attached && @app_observer

        Sketchup.remove_observer(@app_observer) if Sketchup.respond_to?(:remove_observer)
      rescue StandardError => e
        log_exception('detach app observer', e)
      ensure
        @app_observer_attached = false
      end

      def attach_observers(model)
        return unless model
        return if @observed_model.equal?(model)

        detach_observers
        @model_observer ||= ModelObserver.new
        @selection_observer ||= SelectionObserver.new
        model.add_observer(@model_observer)
        model.selection.add_observer(@selection_observer)
        if defined?(EntitiesObserver)
          @entities_observer ||= EntitiesObserver.new
          model.entities.add_observer(@entities_observer)
        end
        @observed_model = model
        record_event('observers_attached', { status: 'SUCCESS' })
      rescue StandardError => e
        log_exception('attach observers', e)
      end

      def detach_observers
        return unless @observed_model

        @observed_model.remove_observer(@model_observer) if @model_observer
        @observed_model.selection.remove_observer(@selection_observer) if @selection_observer
        @observed_model.entities.remove_observer(@entities_observer) if @entities_observer && defined?(EntitiesObserver)
      rescue StandardError => e
        log_exception('detach observers', e)
      ensure
        @observed_model = nil
      end

      def partial_start(stage, message)
        @partial_started = true
        log("B#{stage}: #{message}")
        true
      end

      def runtime_active?
        !!(@runtime_started == true && @running == true && @server_socket &&
          !@server_socket.closed? && @server_thread && @server_thread.alive? && @timer_id)
      end

      def create_dispatch_timer
        @timer_id = UI.start_timer(TICK_INTERVAL, true) { process_commands }
        log('UI dispatch timer created')
      end

      def stop_dispatch_timer
        UI.stop_timer(@timer_id) if @timer_id
      rescue StandardError => e
        log_exception('stop timer', e)
      ensure
        @timer_id = nil
      end

      def start_idle_worker
        @idle_worker = Thread.new do
          sleep(0.1)
        rescue StandardError => e
          log_exception('idle worker', e)
        end
        @idle_worker.abort_on_exception = false
        log('idle background worker created')
      end

      def stop_idle_worker
        thread = @idle_worker
        @idle_worker = nil
        thread.join(0.2) if thread && thread != Thread.current && thread.alive?
      rescue StandardError => e
        log_exception('stop idle worker', e)
      end

      def bind_server
        @server_socket = TCPServer.new(HOST, PORT)
        @server_socket.setsockopt(Socket::SOL_SOCKET, Socket::SO_REUSEADDR, true)
        @bound_port = @server_socket.addr[1]
        log("TCPServer bound to #{HOST}:#{@bound_port}")
      end

      def start_accept_thread
        @server_thread = Thread.new { server_loop }
        @server_thread.abort_on_exception = false
      end

      def server_loop
        log('accept loop started')
        while @running
          server = @server_socket
          break unless server && !server.closed?
          next unless IO.select([server], nil, nil, 0.25)
          client = server.accept_nonblock(exception: false)
          next if client == :wait_readable

          register_client_socket(client)
          worker = Thread.new(client) { |socket| handle_client(socket) }
          worker.abort_on_exception = false
          @client_mutex.synchronize { @client_threads << worker }
          reap_client_threads
        end
      rescue IOError, Errno::EBADF, Errno::EINTR
        raise if @running
      rescue StandardError => e
        log_exception('accept loop', e)
      ensure
        log('accept loop stopped')
      end

      def handle_client(client)
        initialize_state unless @queue_mutex && @command_queue
        result_pending = false
        line = read_line(client, IO_TIMEOUT)
        raise ArgumentError, 'Empty request' if line.nil? || line.empty?
        result_queue = Queue.new
        raise IOError, 'Bridge command queue is unavailable' unless @command_queue
        request = JSON.parse(line)
        request['bridge_transport'] = 'tcp'
        record_event('mcp_connected', { status: 'SUCCESS', request_id: request['request_id'], session_id: request['session_id'], bytes_in: line.bytesize, stage: 'MCP' })
        result_timeout = MODEL_WRITE_ACTIONS.include?(request['action'].to_s) ? MODEL_WRITE_TIMEOUT : IO_TIMEOUT
        @command_queue << { request: request, result_queue: result_queue, expires_at: monotonic_time + result_timeout }
        @queue_mutex.synchronize { @result_queue_count = @result_queue_count.to_i + 1 }
        result_pending = true
        write_response(client, wait_for_result(result_queue, result_timeout))
      rescue StandardError => e
        log_exception('client', e)
        write_response(client, { status: 'error', error: "#{e.class}: #{e.message}" })
      ensure
        if result_pending && @queue_mutex
          @queue_mutex.synchronize { @result_queue_count = [@result_queue_count.to_i - 1, 0].max }
        end
        record_event('mcp_disconnected', { status: 'SUCCESS', stage: 'MCP' }) if line
        unregister_client_socket(client)
        client.close if client && !client.closed?
      end

      def read_line(socket, timeout)
        buffer = +''
        deadline = monotonic_time + timeout
        loop do
          newline = buffer.index("\n")
          return buffer.byteslice(0, newline) if newline
          remaining = deadline - monotonic_time
          raise IOError, 'Request read timeout' if remaining <= 0
          raise IOError, 'Request read timeout' unless IO.select([socket], nil, nil, remaining)
          chunk = socket.read_nonblock(4096, exception: false)
          raise EOFError, 'Client closed before newline' if chunk.nil?
          next if chunk == :wait_readable
          buffer << chunk
          raise ArgumentError, 'Request exceeds 1 MiB' if buffer.bytesize > MAX_REQUEST_BYTES
        end
      end

      def wait_for_result(queue, timeout)
        deadline = monotonic_time + timeout
        loop do
          return queue.pop(true)
        rescue ThreadError
          raise IOError, 'SketchUp command timeout' if monotonic_time >= deadline
          sleep(0.01)
        end
      end

      def process_commands
        queue = @command_queue
        return unless queue
        MAX_COMMANDS_PER_TICK.times do
          command = queue.pop(true)
          if command[:expires_at] && monotonic_time >= command[:expires_at]
            command[:result_queue] << { status: 'error', error: 'WRITE_APPROVAL_EXPIRED' }
            next
          end
          @active_request_deadline = command[:expires_at]
          begin
            command[:result_queue] << dispatch(command[:request])
          ensure
            @active_request_deadline = nil
          end
        rescue ThreadError
          break
        rescue StandardError => e
          log_exception('UI dispatch', e)
          command[:result_queue] << { status: 'error', error: "#{e.class}: #{e.message}" } if command
        end
      end

      def write_response(client, response)
        return unless client && !client.closed?
        client.write(response.to_json << "\n")
      rescue StandardError => e
        log_exception('write response', e)
        nil
      end

      def register_client_socket(socket)
        @client_mutex.synchronize do
          @client_sockets << socket
          @mcp_status = 'CONNECTED'
        end
      end

      def unregister_client_socket(socket)
        return unless @client_mutex

        @client_mutex.synchronize do
          @client_sockets.delete(socket)
          @mcp_status = @client_sockets.empty? ? 'DISCONNECTED' : 'CONNECTED'
        end
      end

      def close_client_sockets
        sockets = @client_mutex ? @client_mutex.synchronize { @client_sockets.dup } : []
        sockets.each { |socket| socket.close unless socket.closed? }
        if @client_mutex
          @client_mutex.synchronize do
            @client_sockets.clear
            @mcp_status = 'DISCONNECTED'
          end
        end
      rescue StandardError => e
        log_exception('close clients', e)
      end

      def close_server_socket
        socket = @server_socket
        @server_socket = nil
        socket.close if socket && !socket.closed?
        @bound_port = nil
      rescue StandardError => e
        log_exception('close server', e)
      end

      def reap_client_threads
        return unless @client_mutex
        @client_mutex.synchronize { @client_threads.delete_if { |thread| !thread.alive? } }
      end

      def cleanup_start_failure
        @running = false
        stop_dispatch_timer
        stop_idle_worker
        stop_instance_registry
        close_server_socket
        close_client_sockets
        @server_thread = nil
        @runtime_started = false
        @partial_started = false
        @command_queue = nil
        @result_queue_count = 0
      rescue StandardError => e
        log_exception('startup cleanup', e)
      end

      def monotonic_time
        Process.clock_gettime(Process::CLOCK_MONOTONIC)
      end

      def mcp_status
        return @mcp_status if @mcp_status

        @client_mutex && @client_mutex.synchronize { @client_sockets.any? ? 'CONNECTED' : 'DISCONNECTED' } || 'DISCONNECTED'
      rescue StandardError
        'DISCONNECTED'
      end

      def log_path
        candidate = ENV.fetch('AI_DG_RUNTIME_LOG', DEFAULT_LOG_PATH)
        protected_log_path?(candidate) ? DEFAULT_LOG_PATH : candidate
      end

      def event_log_path
        candidate = ENV.fetch('AI_DG_EVENT_LOG', DEFAULT_EVENT_LOG_PATH)
        protected_log_path?(candidate) ? DEFAULT_EVENT_LOG_PATH : candidate
      end

      def protected_log_path?(path)
        normalized = path.to_s.tr('\\', '/').upcase.sub(%r{\A//\?/}, '').sub(%r{\A/\?/}, '')
        normalized.match?(/\AD:\//)
      end

      def append_event_log(row)
        FileUtils.mkdir_p(File.dirname(event_log_path))
        File.open(event_log_path, 'a') { |file| file.puts(JSON.generate(row)) }
      rescue StandardError => e
        @last_error = "event log: #{e.class}: #{e.message}"
      end

      def log(message)
        @log_mutex ||= Mutex.new
        @log_mutex.synchronize do
          FileUtils.mkdir_p(File.dirname(log_path))
          File.open(log_path, 'a') do |file|
            timestamp = Time.now.strftime('%Y-%m-%dT%H:%M:%S.%L%z')
            file.puts("#{timestamp} [pid=#{Process.pid} tid=#{Thread.current.object_id}] #{message}")
          end
        end
      rescue StandardError
        nil
      end

      def log_exception(context, error)
        detail = "#{error.class}: #{error.message}"
        detail << "\n#{Array(error.backtrace).join("\n")}" if error.backtrace
        log("#{context} error: #{detail}")
      end
    end

    # Deliberately not `start`: plugin discovery must not bind or block.
    schedule_start
    # A graceful source reload can enter here while an older bridge socket is
    # already live. Bootstrap the new registry immediately so the first
    # router-aware MCP process can discover that existing SketchUp instance.
    start_instance_registry if runtime_active? && !@instance_registry_started
  end
end

# frozen_string_literal: true

# Non-UI-thread client for the persistent Python Agent Host.  This file never
# calls the SketchUp Ruby API; ControlCenter polls messages on a SketchUp timer
# and is the only layer allowed to update HtmlDialog.

require 'json'
require 'open3'
require 'thread'

module AI_DG
  module Bridge
    class AgentHostClient
      MAX_MESSAGES = 500
      MAX_LINE_BYTES = 1_048_576

      attr_reader :last_error

      def initialize(root = 'E:/AI-DG', instance_id = nil)
        @root = root.to_s
        @instance_id = instance_id.to_s.strip
        @mutex = Mutex.new
        @messages = []
        @outgoing = Queue.new
        @sequence = 0
        @started = false
        @stopping = false
        @stdin = @stdout = @stderr = @wait_thread = nil
        @reader_thread = @writer_thread = @stderr_thread = @watcher_thread = nil
        @last_error = nil
      end

      def start
        return true if alive? || @started

        @started = true
        @stopping = false
        @generation = (@generation || 0) + 1
        @outgoing = Queue.new
        @watcher_thread = nil
        @reader_thread = Thread.new { spawn_and_read }
        true
      rescue StandardError => e
        @started = false
        @last_error = e.message
        enqueue({ 'type' => 'agent/event', 'event' => 'host/error', 'data' => { 'error' => 'HOST_START_FAILED', 'detail' => e.class.name } })
        false
      end

      def alive?
        wait = @wait_thread
        wait && wait.alive?
      end

      def snapshot
        {
          'host' => alive? ? 'RUNNING' : (@started ? 'STARTING' : 'STOPPED'),
          'pid' => @wait_thread&.pid,
          'last_error' => @last_error,
          'pending_messages' => @mutex.synchronize { @messages.length }
        }
      end

      def request(method, attributes = {})
        start unless @started
        @sequence += 1
        payload = { 'id' => "ruby-#{@sequence}", 'method' => method }
        attributes.each { |key, value| payload[key.to_s] = value unless value.nil? }
        @outgoing << payload
        payload['id']
      rescue StandardError => e
        @last_error = e.message
        enqueue({ 'type' => 'agent/event', 'event' => 'host/error', 'data' => { 'error' => 'HOST_REQUEST_FAILED', 'detail' => e.class.name } })
        nil
      end

      def poll
        rows = []
        @mutex.synchronize do
          rows = @messages
          @messages = []
        end
        rows
      end

      def stop
        return unless @started

        @stopping = true
        generation = @generation
        @outgoing << { 'id' => "ruby-stop-#{Time.now.to_i}", 'method' => 'host/shutdown' }
        @watcher_thread ||= Thread.new do
          sleep 20
          terminate_owned_process if generation == @generation && alive?
        rescue StandardError
          nil
        end
      rescue StandardError
        terminate_owned_process
      end

      private

      def spawn_and_read
        executable = python_executable
        host_script = File.join(@root, 'agent_host', 'host.py')
        raise LoadError, 'AGENT_HOST_SCRIPT_NOT_FOUND' unless File.file?(host_script)
        raise LoadError, 'PYTHON_RUNTIME_NOT_FOUND' unless executable

        # Keep the host's normal PATH and runtime authentication environment
        # intact. The bridge never reads or logs credentials; Codex/Cline own
        # their authentication and the host only forwards the process env.
        env = ENV.to_h.merge(
          'AI_DG_ROOT' => @root,
          'AI_DG_SKETCHUP_INSTANCE_ID' => @instance_id,
          'PYTHONPATH' => [File.join(@root, 'OUTPUT', 'mcp_deps'), @root, File.join(@root, 'mcp_server'), ENV['PYTHONPATH']].compact.reject(&:empty?).join(File::PATH_SEPARATOR)
        )
        args = [executable]
        args.concat(['-3.12']) if File.basename(executable).downcase == 'py.exe'
        args.concat([host_script, '--root', @root])
        args.concat(['--instance-id', @instance_id]) unless @instance_id.empty?
        @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(env, *args)
        [@stdin, @stdout, @stderr].each(&:binmode)
        start_writer
        start_stderr_reader

        loop do
          line = @stdout.gets
          break unless line
          next if line.bytesize > MAX_LINE_BYTES

          parsed = JSON.parse(line.sub("\uFEFF", ''))
          enqueue(parsed) if parsed.is_a?(Hash)
        rescue JSON::ParserError
          enqueue({ 'type' => 'agent/event', 'event' => 'host/error', 'data' => { 'error' => 'HOST_INVALID_JSON' } })
        rescue IOError, Errno::EPIPE
          break
        end
      rescue StandardError => e
        @last_error = e.message
        enqueue({ 'type' => 'agent/event', 'event' => 'host/error', 'data' => { 'error' => 'HOST_PROCESS_FAILED', 'detail' => e.class.name } })
      ensure
        code = begin
          @wait_thread&.value&.exitstatus
        rescue StandardError
          nil
        end
        enqueue({ 'type' => 'agent/event', 'event' => 'host/exited', 'data' => { 'exit_code' => code } })
        close_pipes
        @started = false
      end

      def start_writer
        @writer_thread = Thread.new do
          loop do
            payload = @outgoing.pop
            break if payload == :stop

            raw = JSON.generate(payload).encode(Encoding::UTF_8)
            next if raw.bytesize > MAX_LINE_BYTES
            @stdin.write(raw)
            @stdin.write("\n")
            @stdin.flush
          rescue IOError, Errno::EPIPE
            break
          rescue StandardError => e
            @last_error = e.message
            break
          end
        end
      end

      def start_stderr_reader
        @stderr_thread = Thread.new do
          loop do
            line = @stderr.gets
            break unless line
            @last_error = line.to_s.strip[0, 500] unless line.to_s.strip.empty?
          end
        rescue IOError
          nil
        end
      end

      def enqueue(message)
        return unless message.is_a?(Hash)

        @mutex.synchronize do
          @messages << message
          @messages = @messages.last(MAX_MESSAGES)
        end
      end

      def close_pipes
        @outgoing << :stop
        [@stdin, @stdout, @stderr].each do |pipe|
          pipe.close unless pipe.nil? || pipe.closed?
        rescue IOError
          nil
        end
        @stdin = @stdout = @stderr = nil
      end

      def terminate_owned_process
        wait = @wait_thread
        return unless wait && wait.alive?

        if Gem.win_platform?
          killer = Process.spawn(File.join(ENV.fetch('SystemRoot', 'C:/Windows'), 'System32/taskkill.exe'), '/PID', wait.pid.to_s, '/T', '/F', out: File::NULL, err: File::NULL)
          Process.detach(killer).join(3)
        else
          Process.kill('TERM', wait.pid)
        end
      rescue Errno::ESRCH, Errno::ECHILD
        nil
      end

      def python_executable
        configured = ENV['AI_DG_PYTHON'].to_s.strip
        user_root = ENV['USERPROFILE'].to_s
        candidates = [
          configured,
          File.join(user_root, 'AppData', 'Local', 'Programs', 'Python', 'Python312', 'python.exe'),
          File.join(user_root, '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'python', 'python.exe'),
          'C:/Windows/py.exe',
          'py.exe',
          'python.exe'
        ].reject(&:empty?)
        candidates.find { |candidate| candidate.include?(':') ? File.file?(candidate) : !`where #{candidate} 2>NUL`.to_s.strip.empty? }
      rescue StandardError
        nil
      end
    end
  end
end

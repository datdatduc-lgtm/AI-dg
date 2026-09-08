# frozen_string_literal: true

require 'json'
require 'open3'

module AI_DG
  module Bridge
    # No SketchUp/UI APIs here. One owned child, bounded output/deadline, and
    # cooperative cancellation. The UI only polls Job; it never joins a worker.
    module HelperProcess
      class Job
        def initialize
          @mutex = Mutex.new
          @cancelled = false
          @done = false
        end

        def start(&work)
          @thread = Thread.new do
            begin
              result = work.call(self)
            rescue StandardError, LoadError => e
              result = { 'status' => 'error', 'error' => 'PROVIDER_HELPER_FAILED', 'detail' => e.class.name }
            ensure
              @mutex.synchronize { @result = result; @done = true }
            end
          end
          self
        end

        def cancel
          @mutex.synchronize { @cancelled = true }
        end

        def cancelled?
          @mutex.synchronize { @cancelled }
        end

        def active?
          @thread && @thread.alive?
        end

        def result
          @mutex.synchronize { @done ? @result : nil }
        end
      end

      module_function

      def monotonic
        Process.clock_gettime(Process::CLOCK_MONOTONIC)
      end

      def failure(code, metadata = {})
        { 'status' => 'error', 'error' => code }.merge(metadata)
      end

      def terminate_child(waiter)
        return unless waiter.alive?

        if Gem.win_platform?
          # Only the PID created by this runner and its descendants, never
          # SketchUp or a process selected by its name.
          killer = Process.spawn(File.join(ENV.fetch('SystemRoot', 'C:/Windows'), 'System32/taskkill.exe'),
                                 '/PID', waiter.pid.to_s, '/T', '/F', out: File::NULL, err: File::NULL)
          killer_wait = Process.detach(killer)
          Process.kill('KILL', killer) unless killer_wait.join(2)
        else
          Process.kill('KILL', -waiter.pid)
        end
      rescue Errno::ESRCH, Errno::ECHILD
        nil
      ensure
        begin
          Process.kill('KILL', waiter.pid) if waiter.alive?
        rescue Errno::ESRCH, Errno::ECHILD
          nil
        end
      end

      def run(env, args, payload, job: nil, timeout: 15, max_output: 1_048_576)
        return failure('AGENT_CANCELLED') if job && job.cancelled?

        input = JSON.generate(payload).encode(Encoding::UTF_8)
        return failure('PROVIDER_HELPER_INPUT_LIMIT') if input.bytesize > 65_536

        deadline = monotonic + timeout
        lock = Mutex.new
        output = { stdout: ''.b, stderr: ''.b }
        bytes = { stdout: 0, stderr: 0 }
        exceeded = false
        reason = nil
        options = Gem.win_platform? ? {} : { pgroup: true }
        Open3.popen3(env, *args, **options) do |stdin, stdout, stderr, waiter|
          [stdin, stdout, stderr].each(&:binmode)
          readers = { stdout: stdout, stderr: stderr }.map do |name, pipe|
            Thread.new do
              loop do
                chunk = pipe.readpartial(8192)
                lock.synchronize do
                  bytes[name] += chunk.bytesize
                  remaining = [max_output - output[name].bytesize, 0].max
                  output[name] << chunk.byteslice(0, remaining)
                  exceeded ||= bytes.values.sum > max_output
                end
              end
            rescue EOFError, IOError
              nil
            end
          end
          writer = Thread.new do
            stdin.write(input)
          rescue IOError, Errno::EPIPE
            nil
          ensure
            stdin.close unless stdin.closed?
          end
          begin
            loop do
              reason = if job && job.cancelled?
                         'AGENT_CANCELLED'
                       elsif lock.synchronize { exceeded }
                         'PROVIDER_HELPER_OUTPUT_LIMIT'
                       elsif monotonic >= deadline
                         'PROVIDER_HELPER_TIMEOUT'
                       end
              if reason
                terminate_child(waiter)
                break
              end
              break unless waiter.alive?

              waiter.join(0.03)
            end
            readers.each { |reader| reader.join(0.2) }
            metadata = lock.synchronize { { 'stdout_bytes' => bytes[:stdout], 'stderr_bytes' => bytes[:stderr] } }
            reason ||= 'PROVIDER_HELPER_OUTPUT_LIMIT' if lock.synchronize { exceeded }
            return failure(reason, metadata) if reason

            raw = lock.synchronize { output[:stdout].dup }.force_encoding(Encoding::UTF_8)
            return failure('PROVIDER_HELPER_INVALID_RESPONSE', metadata) unless raw.valid_encoding?

            parsed = parse_response(raw.sub("\uFEFF", '').strip)
            status = waiter.value
            # Keep structured failures from exit 1, but never bless a success
            # JSON from a failed process. Do not include child output/secrets.
            return parsed if parsed.is_a?(Hash) && (status.success? || parsed['status'].to_s != 'ok')

            failure(status.success? ? 'PROVIDER_HELPER_INVALID_RESPONSE' : 'PROVIDER_HELPER_PROCESS_FAILED',
                    metadata.merge('exit_code' => status.exitstatus))
          ensure
            terminate_child(waiter) if waiter.alive?
            [stdin, stdout, stderr].each { |pipe| pipe.close unless pipe.closed? }
            ([writer] + readers).each { |thread| thread.join(0.2) }
          end
        end
      rescue StandardError => e
        failure('PROVIDER_HELPER_PROCESS_FAILED', 'detail' => e.class.name)
      end

      def parse_response(raw)
        candidate = JSON.parse(raw)
        candidate if candidate.is_a?(Hash)
      rescue JSON::ParserError
        raw.lines.reverse_each do |line|
          begin
            candidate = JSON.parse(line)
            return candidate if candidate.is_a?(Hash)
          rescue JSON::ParserError
            next
          end
        end
        nil
      end
    end
  end
end

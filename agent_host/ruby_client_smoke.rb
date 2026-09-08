require_relative '../bridge_sketchup/ai_dg_bridge/agent_host_client'

instance_id = "su-#{Process.pid}-a1b2c3d4"
client = AI_DG::Bridge::AgentHostClient.new(File.expand_path('..', __dir__), instance_id)
begin
  request_id = client.request('host/status')
  deadline = Time.now + 15
  response = nil
  until response || Time.now >= deadline
    response = client.poll.find { |message| message['id'] == request_id }
    sleep 0.05 unless response
  end
  raise 'Ruby client failed to reach real host' unless response && response['status'] == 'ok'
  raise 'Ruby client lost SketchUp instance scope' unless response.dig('data', 'instance_id') == instance_id
  puts 'RUBY_HOST_IPC_PASS'
ensure
  client.stop
  deadline = Time.now + 25
  sleep 0.05 while client.alive? && Time.now < deadline
  raise 'Ruby client left host alive' if client.alive?
end

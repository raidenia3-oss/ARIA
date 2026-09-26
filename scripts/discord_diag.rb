#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "socket"
require "net/http"
require "time"

def check_tcp(host, port, timeout = 3)
  begin
    s = TCPSocket.new(host, port)
    s.close
    true
  rescue StandardError
    false
  end
end

def check_http(url, timeout = 5)
  uri = URI.parse(url)
  uri.path = "/health"
  Net::HTTP.start(uri.host, uri.port, read_timeout: timeout, open_timeout: timeout) do |http|
    req = Net::HTTP::Get.new(uri.request_uri)
    res = http.request(req)
    res.is_a?(Net::HTTPSuccess)
  rescue StandardError
    false
  end
end

def check_discord_process
  result = `tasklist /FI "IMAGENAME eq ruby.exe" 2>NUL`
  result.include?("ruby.exe") && result.include?("bot.rb")
end

token = ENV["DISCORD_BOT_TOKEN"]
client_id = ENV["DISCORD_CLIENT_ID"]
backend_url = ENV["AURA_BACKEND_URL"] || "http://localhost:8000"
redis_url = ENV["REDIS_URL"] || "redis://localhost:6379/0"

backend_host, backend_port = begin
  backend_url.match(%r{^https?://([^:]+):(\d+)}).then { |m| [m ? m[1] : "localhost", m ? m[2].to_i : 8000] }
rescue StandardError
  ["localhost", 8000]
end

redis_host, redis_port = begin
  redis_url.match(%r{redis://([^:]+):(\d+)})&.then { |m| [m[1], m[2].to_i] }
rescue StandardError
  ["localhost", 6379]
end

backend_ok = check_http(backend_url)
redis_ok = check_tcp(redis_host, redis_port)
process_running = check_discord_process

token_present = !token.nil? && !token.strip.empty?
client_id_present = !client_id.nil? && !client_id.strip.empty?

def mask_token(token)
  return "[ausente]" if token.nil? || token.strip.empty?
  t = token.strip
  return "****" if t.length <= 8
  "#{t[0..3]}****#{t[-4..]}"
end

def validate_token(token)
  return "absent" if token.nil? || token.strip.empty?
  t = token.strip
  return "invalid" if t.length < 10
  parts = t.split(".")
  if parts.length != 3 || parts[0].empty? || parts[1].empty? || parts[2].empty?
    "invalid"
  else
    "configured"
  end
end

token_validation = validate_token(token)

diag = {
  timestamp: Time.now.iso8601,
  status: nil,
  discord: {
    token_validation: token_validation,
    token_masked: mask_token(token),
    client_id_configured: client_id_present,
    bot_process_running: process_running,
  },
  backend: {
    url: backend_url,
    reachable: backend_ok,
  },
  redis: {
    url: redis_url,
    reachable: redis_ok,
  },
}

issues = []
issues.append("DISCORD_BOT_TOKEN no configurado") if token_validation == "absent"
issues.append("DISCORD_BOT_TOKEN presente pero con formato inválido") if token_validation == "invalid"
issues.append("DISCORD_CLIENT_ID no configurado") unless client_id_present
issues.append("Backend no disponible en #{backend_url}") unless backend_ok
issues.append("Redis no disponible en #{redis_url}") unless redis_ok
issues.append("Proceso de bot de Discord no detectado") unless process_running

if token_validation == "absent" && !client_id_present
  diag[:status] = "not_configured"
elsif process_running && backend_ok && redis_ok && token_validation == "configured"
  diag[:status] = "healthy"
elsif !process_running && backend_ok && token_validation == "configured"
  diag[:status] = "offline"
elsif issues.any?
  diag[:status] = "degraded"
else
  diag[:status] = "degraded"
end

diag[:issues] = issues
puts JSON.pretty_generate(diag)

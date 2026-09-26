#!/usr/bin/env ruby
# frozen_string_literal: true

# AURA Discord Bot — Wrapper with reconnection
# Usage: ruby start-discord-bot.rb [retries]
#
# Reconnect behavior:
# - Bot disconnects → log error → wait 5s → retry
# - Max retries: 10 (or pass as arg)
# - Never logs token value

require "bundler/setup"
require "json"

# Load environment from discord-bot .env directory
begin
  require "dotenv"
  Dotenv.load(
    File.expand_path("../services/discord-bot/.env", __dir__),
    File.expand_path("../services/discord-bot/.env.local", __dir__)
  )
rescue LoadError
  nil
end

# Prevent duplicate instances — check by lock file PID
lock_file = File.expand_path("../data/discord_bot.lock", __dir__)
require "fileutils"
FileUtils.mkdir_p(File.dirname(lock_file))

if File.exist?(lock_file)
  existing_pid = File.read(lock_file).to_i
  if existing_pid > 0 && existing_pid != Process.pid
    is_running = false
    is_running = true if File.exist?("/proc/#{existing_pid}")
    if !is_running
      ps_out = `tasklist /FI "PID eq #{existing_pid}" 2>NUL`
      is_running = ps_out.include?(existing_pid.to_s) && ps_out.include?("ruby")
    end
    if is_running
      puts "[DiscordBot] Another instance is already running (PID #{existing_pid}). Exiting."
      exit 0
    end
  end
end

File.write(lock_file, Process.pid.to_s)

max_retries = (ARGV[0] || 10).to_i
retry_delay = 5
attempt = 0

loop do
  attempt += 1
  puts "[DiscordBot] Starting (attempt #{attempt}/#{max_retries})"

   begin
    $LOADED_FEATURES.delete_if { |f| f.include?("bot.rb") && f.include?("discord-bot") }
    require_relative "../services/discord-bot/bot"
    # Skip command registration on retries (commands already registered)
    config = attempt > 1 ? { skip_command_registration: true } : {}
    bot = Aura::DiscordBot.new(config)
    bot.start
    puts "[DiscordBot] Bot stopped normally."
  rescue SystemExit => e
    puts "[DiscordBot] Process exited with code #{e.status}"
  rescue StandardError => e
    puts "[DiscordBot] Error: #{e.class}: #{e.message}"
    puts "[DiscordBot] Backtrace: #{e.backtrace.first(5).join("\n  ")}"
  end

  if attempt >= max_retries
    puts "[DiscordBot] Max retries (#{max_retries}) reached. Exiting."
    exit 1
  end

  puts "[DiscordBot] Retrying in #{retry_delay}s..."
  sleep retry_delay
end

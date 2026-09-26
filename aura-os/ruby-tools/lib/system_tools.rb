#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/system_tools.rb

require 'sys/proctable'
require 'json'
require 'time'
require 'timeout'
require 'net/http'
require 'etc'

module AuraTools
  class SystemTools

    def self.cpu_usage
      begin
        loadavg_file = '/proc/loadavg'
        if File.exist?(loadavg_file)
          load_avg = File.read(loadavg_file).split
          cpu_count = File.read('/proc/cpuinfo').scan(/^processor\s*:/).size
        else
          load_avg = `uptime 2>/dev/null`.split('average:').last&.split(',')&.map(&:strip) || ['0', '0', '0']
          cpu_count = Etc.nprocessors rescue 1
        end

        {
          load_avg_1m: load_avg[0],
          load_avg_5m: load_avg[1],
          load_avg_15m: load_avg[2],
          cpu_count: cpu_count,
          timestamp: Time.now.iso8601
        }
      rescue => e
        { error: e.message }
      end
    end

    def self.memory_usage
      begin
        if File.exist?('/proc/meminfo')
          meminfo = File.read('/proc/meminfo')
          total = meminfo.match(/MemTotal:\s+(\d+)/)[1].to_i
          available = meminfo.match(/MemAvailable:\s+(\d+)/)[1].to_i
          used = total - available
          {
            total_kb: total,
            used_kb: used,
            available_kb: available,
            percentage: ((used.to_f / total) * 100).round(2),
            timestamp: Time.now.iso8601
          }
        else
          { error: "Memory info not available on this system" }
        end
      rescue => e
        { error: e.message }
      end
    end

    def self.list_processes
      begin
        processes = Sys::ProcTable.ps.map { |p|
          {
            pid: p.pid,
            name: p.comm,
            state: p.state,
            etime: p.etime,
            rss_mb: (p.rss.to_f / 1024).round(2)
          }
        }

        {
          processes: processes,
          count: processes.length,
          timestamp: Time.now.iso8601
        }
      rescue => e
        { error: e.message }
      end
    end

    def self.find_process(name)
      begin
        processes = Sys::ProcTable.ps.select { |p| p.comm.include?(name) }

        {
          name: name,
          found: processes.length,
          processes: processes.map { |p| {
            pid: p.pid,
            name: p.comm,
            state: p.state,
            rss_mb: (p.rss.to_f / 1024).round(2)
          }},
          timestamp: Time.now.iso8601
        }
      rescue => e
        { error: e.message }
      end
    end

    def self.uptime
      begin
        if File.exist?('/proc/uptime')
          up_seconds = File.read('/proc/uptime').split[0].to_f
        else
          up_seconds = `systemctl show -p ActiveEnterTimestamp 2>/dev/null`
          up_seconds = 0
        end

        {
          uptime_seconds: up_seconds.round(0).to_i,
          uptime_human: format_uptime(up_seconds.to_i),
          timestamp: Time.now.iso8601
        }
      rescue => e
        { error: e.message }
      end
    end

    def self.execute_command(cmd, timeout: 30)
      begin
        output = Timeout.timeout(timeout) do
          `#{cmd} 2>&1`
        end

        {
          command: cmd,
          success: true,
          output: output,
          timestamp: Time.now.iso8601
        }
      rescue Timeout::Error
        {
          command: cmd,
          success: false,
          error: "Command timed out after #{timeout}s",
          timestamp: Time.now.iso8601
        }
      rescue => e
        {
          command: cmd,
          success: false,
          error: e.message,
          timestamp: Time.now.iso8601
        }
      end
    end

    private

    def self.format_uptime(seconds)
      days = seconds / 86400
      hours = (seconds % 86400) / 3600
      minutes = (seconds % 3600) / 60

      "#{days}d #{hours}h #{minutes}m"
    end
  end
end

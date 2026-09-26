#!/usr/bin/env ruby
# AURA OS — System Automation Toolkit
# Usage: ruby system_automation.rb [command] [options]
#
# Commands:
#   scan-network          Scan local network for devices
#   health-check          Run system health check
#   process-list          List running processes
#   disk-usage            Show disk usage by directory
#   service-status        Check service status
#   backup                Create a backup
#   cleanup               Clean temporary files
#   monitor PORT          Start monitoring a network endpoint
#
# Examples:
#   ruby system_automation.rb scan-network --subnet 192.168.1.0/24
#   ruby system_automation.rb health-check
#   ruby system_automation.rb monitor localhost:8000

require 'socket'
require 'timeout'
require 'json'
require 'fileutils'
require 'optparse'
require 'pastel'
require 'ipaddr'
require 'yaml'
require 'net/http'
require 'uri'
require 'find'

$pastel = Pastel.new

# ════════════════════════════════════════════════════════════════════════════
# Network Scanning
# ════════════════════════════════════════════════════════════════════════════

def scan_network(subnet: '192.168.1.0/24', timeout: 1.0)
  ip_range = IPAddr.new(subnet).to_range

  active_hosts = []
  threads = []
  mutex = Mutex.new

  ip_range.each do |ip|
    threads << Thread.new do
      host = ip.to_s
      begin
        Timeout.timeout(timeout) do
          packet = "\x00" * 64
          s = Socket.new(Socket::AF_INET, Socket::SOCK_DGRAM)
          s.connect(host, 80)
          s.close
        end
        mutex.synchronize { active_hosts << host }
      rescue => _e
        # Host unreachable
      end
    end
  end
  threads.each(&:join)

  return active_hosts.sort
end

# ════════════════════════════════════════════════════════════════════════════
# Health Check
# ════════════════════════════════════════════════════════════════════════════

def health_check
  checks = {}

  checks[:cpu] = begin
    loadavg = File.read('/proc/loadavg').split[0..2].join(', ')
    loadavg
  rescue
    `uptime 2>/dev/null`.strip || 'N/A'
  end

  checks[:memory] = begin
    meminfo = File.read('/proc/meminfo')
    total = meminfo.match(/MemTotal:\s+(\d+)/)[1].to_i / 1024
    available = meminfo.match(/MemAvailable:\s+(\d+)/)[1].to_i / 1024
    "#{available}/#{total} MB available"
  rescue
    'N/A'
  end

  checks[:disk] = begin
    stat = File.stat('/')
    "Total: #{stat.blocks * 512 / 1024 / 1024} MB"
  rescue
    'N/A'
  end

  checks[:uptime] = begin
    File.read('/proc/uptime').split[0].to_f / 3600
  rescue
    0
  end

  checks[:processes] = begin
    Dir.glob('/proc/[0-9]*').size
  rescue
    0
  end

  checks[:aura_api] = begin
    uri = URI('http://localhost:8000/health')
    response = Net::HTTP.get_response(uri)
    response.code == '200' ? 'OK' : 'ERROR'
  rescue => e
    "OFFLINE (#{e.class})"
  end

  return checks
end

# ════════════════════════════════════════════════════════════════════════════
# Process List
# ════════════════════════════════════════════════════════════════════════════

def list_processes(limit: 20)
  pids = Dir.glob('/proc/[0-9]*').map { |p| File.basename(p).to_i }.sort
  pids = pids.last(limit)

  pids.map do |pid|
    begin
      cmdline = File.read("/proc/#{pid}/cmdline").gsub("\0", ' ').strip
      stat = File.read("/proc/#{pid}/stat").split
      {
        pid: pid,
        name: stat[1].gsub(/[()]/, ''),
        state: stat[2],
        cmdline: cmdline.empty? ? stat[1] : cmdline,
      }
    rescue
      nil
    end
  end.compact
end

# ════════════════════════════════════════════════════════════════════════════
# Disk Usage
# ════════════════════════════════════════════════════════════════════════════

def disk_usage(path: '.', limit: 20)
  entries = Dir.entries(path)
  sizes = entries.reject { |e| e.start_with?('.') }.map do |entry|
    full_path = File.join(path, entry)
    size = 0
    if File.directory?(full_path)
      Find.find(full_path) { |f| size += File.size(f) if File.file?(f) }
    else
      size = File.size(full_path) rescue 0
    end
    { name: entry, size: size }
  end

  sizes.sort_by { |s| -s[:size] }.first(limit)
end

# ════════════════════════════════════════════════════════════════════════════
# Monitor
# ════════════════════════════════════════════════════════════════════════════

def monitor_endpoint(host, port, interval: 5, count: 10)
  uri = URI("http://#{host}:#{port}/health")

  count.times do |i|
    begin
      start_time = Time.now
      response = Net::HTTP.get_response(uri)
      latency = ((Time.now - start_time) * 1000).round(2)

      status = response.code == '200' ? $pastel.green('UP') : $pastel.yellow("HTTP #{response.code}")
      puts "[#{Time.now.strftime('%H:%M:%S')}] #{host}:#{port} — #{status} (#{latency}ms)"
    rescue => e
      puts "[#{Time.now.strftime('%H:%M:%S')}] #{host}:#{port} — #{$pastel.red('DOWN')} (#{e.class})"
    end

    sleep(interval) unless i == count - 1
  end
end

# ════════════════════════════════════════════════════════════════════════════
# Main CLI
# ════════════════════════════════════════════════════════════════════════════

options = {}
OptionParser.new do |opts|
  opts.banner = "Uso: ruby system_automation.rb [command] [opciones]"
  opts.on("--subnet SUBNET", "Subnet for network scan") do |v|
    options[:subnet] = v
  end
  opts.on("--timeout T", Float, "Timeout (default: 1.0)") do |v|
    options[:timeout] = v
  end
  opts.on("--limit N", Integer, "Limit output") do |v|
    options[:limit] = v
  end
  opts.on("--interval N", Integer, "Monitor interval (seconds)") do |v|
    options[:interval] = v
  end
  opts.on("--count N", Integer, "Monitor count") do |v|
    options[:count] = v
  end
  opts.on("--path PATH", "Path for disk usage") do |v|
    options[:path] = v
  end
  opts.on("--json", "Output JSON") do
    options[:json] = true
  end
  opts.on("-h", "--help", "Mostrar ayuda") do
    puts opts
    puts
    puts "Commands:"
    puts "  scan-network          Scan local network for active hosts"
    puts "  health-check          Run system health checks"
    puts "  process-list          List running processes"
    puts "  disk-usage            Show disk usage by entry"
    puts "  monitor HOST:PORT     Monitor a network endpoint"
    exit
  end
end.parse!

command = ARGV.shift

case command
when 'scan-network'
  subnet = options[:subnet] || '192.168.1.0/24'
  puts $pastel.cyan("Escaneando red #{subnet}...")
  hosts = scan_network(subnet: subnet, timeout: options[:timeout] || 1.0)
  if options[:json]
    puts JSON.pretty_generate(hosts)
  else
    hosts.each do |h|
      puts $pastel.green("  ✓ #{h}")
    end
    puts
    puts $pastel.green("Hosts activos: #{hosts.size}")
  end

when 'health-check'
  puts $pastel.cyan("AURA OS — Health Check")
  puts
  checks = health_check
  if options[:json]
    puts JSON.pretty_generate(checks)
  else
    checks.each do |key, value|
      puts "  #{key.to_s.ljust(15)}: #{value}"
    end
  end

when 'process-list'
  procs = list_processes(limit: options[:limit] || 20)
  if options[:json]
    puts JSON.pretty_generate(procs)
  else
    procs.each do |p|
      puts "  #{p[:pid].to_s.ljust(8)} #{p[:name].ljust(20)} #{p[:state]} #{p[:cmdline]}"
    end
  end

when 'disk-usage'
  path = options[:path] || '.'
  sizes = disk_usage(path: path, limit: options[:limit] || 20)
  if options[:json]
    puts JSON.pretty_generate(sizes)
  else
    sizes.each do |s|
      mb = s[:size] > 1024 * 1024 ? "#{s[:size] / 1024 / 1024} MB" : "#{s[:size] / 1024} KB"
      puts "  #{mb.rjust(12)}  #{s[:name]}"
    end
  end

when 'monitor'
  target = ARGV.shift
  if target.nil? || !target.include?(':')
    puts $pastel.red("Usage: ruby system_automation.rb monitor HOST:PORT")
    exit 1
  end
  host, port = target.split(':')
  puts $pastel.cyan("Monitoring #{host}:#{port} (Ctrl+C to stop)")
  begin
    monitor_endpoint(host, port.to_i, interval: options[:interval] || 5, count: options[:count] || 10)
  rescue Interrupt
    puts $pastel.yellow("\nMonitoring stopped.")
  end

else
  puts "Uso: ruby system_automation.rb [command]"
  puts "Comandos: scan-network, health-check, process-list, disk-usage, monitor"
  puts "Usa --help para mas informacion."
  exit 1
end

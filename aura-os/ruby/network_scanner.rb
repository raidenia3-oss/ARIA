#!/usr/bin/env ruby
# AURA OS — Advanced Network Scanner
# Usage: ruby network_scanner.rb [options]
#
# Examples:
#   ruby network_scanner.rb --scan 192.168.1.1 --ports 1-1000
#   ruby network_scanner.rb --scan 192.168.1.0/24 --top-ports 100

require 'socket'
require 'timeout'
require 'time'
require 'optparse'
require 'ipaddr'
require 'json'
require 'thread'
require 'pastel'

$scan_results = []
$mutex = Mutex.new
$pastel = Pastel.new

TOP_PORTS = [
  21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 161, 162, 389, 443,
  445, 465, 587, 636, 993, 995, 1433, 1521, 2525, 3306, 3389, 5432,
  5667, 5900, 5984, 6379, 6660, 6661, 6662, 6663, 6664, 6665, 6666,
  6667, 6668, 6669, 6697, 7001, 7002, 8000, 8008, 8080, 8081, 8443,
  8544, 8686, 9000, 9042, 9090, 9092, 9200, 9300, 9418, 9999, 11211,
  15672, 27017, 27018, 27019, 27020, 27021, 27022, 27023, 27024, 27025,
  27026, 50000, 50001, 50002, 50003, 50004, 50005, 50006, 50007, 50008,
  50009, 50010, 65535,
].freeze

def parse_ports(port_str)
  if port_str.end_with?('-')
    start_p = port_str[0..-2].to_i
    (start_p..65535).to_a
  elsif port_str.include?('-')
    start_p, end_p = port_str.split('-').map(&:to_i)
    (start_p..end_p).to_a
  elsif port_str == 'top'
    TOP_PORTS
  else
    port_str.split(',').map(&:to_i)
  end
end

def parse_target(target)
  if target.include?('/')
    ip, prefix = target.split('/')
    ip_addr = IPAddr.new(ip)
    ip_addr.to_range.to_a
  else
    [target]
  end
end

def scan_port(host, port, timeout: 2.0)
  begin
    socket = Socket.tcp(host, port, connect_timeout: timeout, &->(s) { s.close })
    return :open
  rescue Errno::ECONNREFUSED
    return :closed
  rescue Errno::EHOSTUNREACH, Errno::EHOSTUNREACH, Timeout::Error, Errno::ETIMEDOUT
    return :filtered
  rescue => _e
    return :unknown
  end
end

def scan_host(host, ports, threads: 100, timeout: 2.0)
  queue = Queue.new
  ports.each { |p| queue << p }
  workers = []

  threads.times do
    workers << Thread.new do
      while port = queue.pop(true) rescue nil
        status = scan_port(host, port, timeout: timeout)
        $mutex.synchronize do
          $scan_results << {
            host: host,
            port: port,
            status: status.to_s,
            timestamp: Time.now.utc.iso8601,
          }
        rescue => e
          $mutex.synchronize do
            $scan_results << {
              host: host,
              port: port,
              status: 'error',
              timestamp: Time.now.utc.iso8601,
            }
          end
        end
      end
    end
  end
  workers.each(&:join)
end

options = {}
OptionParser.new do |opts|
  opts.banner = "Uso: ruby network_scanner.rb [opciones]"
  opts.on("--scan TARGET", "IP o red a escanear (192.168.1.1 o 192.168.1.0/24)") do |v|
    options[:target] = v
  end
  opts.on("--ports PORTS", "Puertos (1-1000, 80,443,22, 'top')") do |v|
    options[:ports] = v
  end
  opts.on("--threads N", Integer, "Numero de threads (default: 100)") do |v|
    options[:threads] = v
  end
  opts.on("--timeout T", Float, "Timeout en segundos (default: 2.0)") do |v|
    options[:timeout] = v
  end
  opts.on("--json", "Output en formato JSON") do
    options[:json] = true
  end
  opts.on("--top-ports N", Integer, "Escanear top N puertos comunes") do |v|
    options[:top_ports] = v
  end
  opts.on("-h", "--help", "Mostrar ayuda") do
    puts opts
    exit
  end
end.parse!

if options[:target].nil?
  puts $pastel.red("ERROR: Debes especificar un target con --scan")
  exit 1
end

targets = parse_target(options[:target])
ports_str = options[:ports] || options[:top_ports] ? "1-1000" : "top"
ports = parse_ports(ports_str)
threads = options[:threads] || 100
timeout = options[:timeout] || 2.0

puts $pastel.cyan("AURA Network Scanner v1.0")
puts $pastel.dim("Target: #{targets.join(', ')} | Ports: #{ports.size} | Threads: #{threads}")
puts

targets.each do |host|
  puts $pastel.yellow("Escaneando #{host}...")
  scan_host(host, ports, threads: threads, timeout: timeout)
end

open_ports = $scan_results.select { |r| r[:status] == 'open' }
filtered_ports = $scan_results.select { |r| r[:status] == 'filtered' }

if options[:json]
  puts JSON.pretty_generate($scan_results)
else
  open_ports.each do |r|
    puts $pastel.green("  ✓ #{r[:host]}:#{r[:port]} - #{r[:status]}")
  end
  filtered_ports.each do |r|
    puts $pastel.yellow("  ? #{r[:host]}:#{r[:port]} - #{r[:status]}")
  end

  closed_count = $scan_results.count { |r| r[:status] == 'closed' }
  puts
  puts $pastel.green("Puertos abiertos: #{open_ports.size}")
  puts $pastel.yellow("Puertos filtrados: #{filtered_ports.size}")
  puts $pastel.red("Puertos cerrados: #{closed_count}")
end

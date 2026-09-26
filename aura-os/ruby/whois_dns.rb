#!/usr/bin/env ruby
# AURA OS — WHOIS & DNS Query Tool
# Usage: ruby whois_dns.rb [options]
#
# Examples:
#   ruby whois_dns.rb --whois example.com
#   ruby whois_dns.rb --dns example.com
#   ruby whois_dns.rb --all example.com

require 'socket'
require 'timeout'
require 'optparse'
require 'json'
require 'resolv'
require 'pastel'

$pastel = Pastel.new

WHP_SERVERS = {
  com: 'whois.verisign-grs.com',
  net: 'whois.verisign-grs.com',
  org: 'whois.pir.org',
  io: 'whois.nic.io',
  info: 'whois.iana.org',
  com_mx: 'whois.iana.org',
}.freeze

def whois_lookup(domain, server: 'whois.iana.org', port: 43, timeout: 10)
  begin
    TCPSocket.open(server, port) do |sock|
      sock.puts(domain)
      sock.shutdown(Socket::SHUT_WR)

      response = ''
      Timeout.timeout(timeout) do
        while (line = sock.gets)
          response += line
        end
      end
      return response
    end
  rescue => e
    return "Error: #{e.message}"
  end
end

def find_whois_server(domain)
  # IANA referral lookup
  response = whois_lookup(domain, server: 'whois.iana.org')
  if response =~ /refer:\s*(\S+)/
    return Regexp.last_match(1)
  end
  return 'whois.iana.org'
end

def dns_lookup(domain, record_type = 'A')
  begin
    case record_type.upcase
    when 'A'
      Resolv::DNS.open do |dns|
        return dns.getaddress(domain).to_s
      end
    when 'AAAA'
      Resolv::DNS.open do |dns|
        return dns.getaddress(domain).to_name rescue nil
      end
    when 'MX'
      Resolv::DNS.open do |dns|
        return dns.getresources(domain, Resolv::DNS::Resource::IN::MX).map(&:exchange).map(&:to_s)
      end
    when 'TXT'
      Resolv::DNS.open do |dns|
        return dns.getresources(domain, Resolv::DNS::Resource::IN::TXT).map(&:data).map(&:to_s)
      end
    when 'NS'
      Resolv::DNS.open do |dns|
        return dns.getresources(domain, Resolv::DNS::Resource::IN::NS).map(&:server).map(&:to_s)
      end
    when 'CNAME'
      Resolv::DNS.open do |dns|
        return dns.getresources(domain, Resolv::DNS::Resource::IN::CNAME).map(&:name).map(&:to_s)
      end
    else
      return "Unknown record type: #{record_type}"
    end
  rescue Resolv::ResolvError => e
    return "DNS Error: #{e.message}"
  rescue => e
    return "Error: #{e.message}"
  end
end

def reverse_dns(ip)
  begin
    return Resolv.getname(ip).to_s
  rescue Resolv::ResolvError
    return "No PTR record found"
  rescue => e
    return "Error: #{e.message}"
  end
end

options = {}
OptionParser.new do |opts|
  opts.banner = "Uso: ruby whois_dns.rb [opciones]"
  opts.on("--whois DOMINIO", "WHOIS lookup") do |v|
    options[:whois] = v
  end
  opts.on("--dns DOMINIO", "DNS A record lookup") do |v|
    options[:dns] = v
  end
  opts.on("--dns-all DOMINIO", "All DNS records (A, AAAA, MX, TXT, NS, CNAME)") do |v|
    options[:dns_all] = v
  end
  opts.on("--all DOMINIO", "WHOIS + all DNS records") do |v|
    options[:all] = v
  end
  opts.on("--reverse IP", "Reverse DNS lookup") do |v|
    options[:reverse] = v
  end
  opts.on("--server SERVER", "Custom WHOIS server") do |v|
    options[:server] = v
  end
  opts.on("--json", "Output JSON") do
    options[:json] = true
  end
  opts.on("-h", "--help", "Mostrar ayuda") do
    puts opts
    exit
  end
end.parse!

def output(data, as_json: false)
  if as_json
    puts JSON.pretty_generate(data)
  else
    puts data
  end
end

if options[:whois]
  domain = options[:whois]
  server = options[:server] || find_whois_server(domain)
  puts $pastel.cyan("WHOIS: #{domain}")
  puts $pastel.dim("Server: #{server}")
  puts
  result = whois_lookup(domain, server: server)
  output(result, as_json: options[:json])
elsif options[:dns]
  domain = options[:dns]
  puts $pastel.cyan("DNS A record: #{domain}")
  result = dns_lookup(domain, 'A')
  puts result
elsif options[:dns_all]
  domain = options[:dns_all]
  puts $pastel.cyan("DNS Records: #{domain}")
  puts
  ['A', 'MX', 'TXT', 'NS', 'CNAME'].each do |type|
    result = dns_lookup(domain, type)
    puts $pastel.yellow("#{type}:")
    puts result
    puts
  end
elsif options[:all]
  domain = options[:all]
  puts $pastel.cyan("=== WHOIS + DNS: #{domain} ===\n\n")

  server = options[:server] || find_whois_server(domain)
  puts $pastel.green("--- WHOIS ---")
  puts $pastel.dim("Server: #{server}\n\n")
  whois_result = whois_lookup(domain, server: server)
  puts whois_result
  puts

  puts $pastel.green("--- DNS ---")
  ['A', 'MX', 'TXT', 'NS'].each do |type|
    result = dns_lookup(domain, type)
    puts $pastel.yellow("#{type}: #{result}")
  end
  puts
elsif options[:reverse]
  ip = options[:reverse]
  puts $pastel.cyan("Reverse DNS: #{ip}")
  result = reverse_dns(ip)
  puts result
else
  puts "Uso: ruby whois_dns.rb [opciones]"
  puts "Usa --help para mas informacion."
  exit 1
end

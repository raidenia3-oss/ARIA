#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/network_scanner.rb

require 'net/ping'
require 'nmap/parser'
require 'ipaddress'
require 'json'
require 'time'
require 'open3'

module AuraTools
  class NetworkScanner

    def initialize(timeout: 5)
      @timeout = timeout
    end

    def ping(host)
      begin
        result = Net::Ping::External.new(host)
        {
          host: host,
          reachable: result.ping?,
           time_ms: begin
             (result.duration * 1000).round(2)
           rescue
             nil
           end,
          timestamp: Time.now.iso8601
        }
      rescue => e
        {
          host: host,
          reachable: false,
          error: e.message,
          timestamp: Time.now.iso8601
        }
      end
    end

    def scan_network(cidr, quiet: false)
      begin
        network = IPAddress(cidr)
      rescue ArgumentError => e
        return { error: "Invalid CIDR: #{e.message}", timestamp: Time.now.iso8601 }
      end

      live_hosts = []

      network.each_host do |ip|
        puts "[*] Scanning #{ip}..." unless quiet

        if ping(ip.to_s)[:reachable]
          live_hosts << ip.to_s
        end
      end

      {
        network: cidr,
        live_hosts: live_hosts,
        total_scanned: network.size - 2,
        timestamp: Time.now.iso8601
      }
    end

    def scan_ports(host, ports: "1-65535", args: "-sV")
      begin
        cmd = "nmap -oX - #{args} -p #{ports} #{host}"
        stdout, stderr, status = Open3.capture3(cmd)

        if status.success?
          parser = Nmap::Parser.new(stdout)

          results = parser.hosts.map do |h|
            {
              host: h.ip,
              ports: h.ports.map { |p| {
                port: p.number,
                protocol: p.protocol,
                state: p.state,
                service: p.service,
                version: p.service_extrainfo
              }},
              os: h.os_guess
            }
          end

          { success: true, data: results, timestamp: Time.now.iso8601 }
        else
          { success: false, error: stderr, timestamp: Time.now.iso8601 }
        end
      rescue => e
        { success: false, error: e.message, timestamp: Time.now.iso8601 }
      end
    end

    def traceroute(host, max_hops: 30)
      begin
        cmd = "traceroute -m #{max_hops} #{host}"
        stdout, stderr, status = Open3.capture3(cmd)

        hops = stdout.split("\n").map { |line|
          parts = line.strip.split(/\s+/)
          {
            hop: parts[0].to_i,
            host: parts[1],
            ip: parts[2]&.gsub(/[()]/, ""),
            times: parts[3..5]&.map(&:to_f)
          }
        }

        { success: true, target: host, hops: hops, timestamp: Time.now.iso8601 }
      rescue => e
        { success: false, error: e.message, timestamp: Time.now.iso8601 }
      end
    end

    def local_network_info
      require 'socket'

      {
        hostname: Socket.gethostname,
        local_ip: Socket.ip_address_list.map(&:ip_address).reject { |ip| ip.start_with?("127") }.first,
        fqdn: Socket.gethostbyname(Socket.gethostname)[0],
        timestamp: Time.now.iso8601
      }
    end
  end
end

#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/dns_resolver.rb

require 'net/dns'
require 'httparty'
require 'json'
require 'time'

module AuraTools
  class DNSResolver

    def initialize
      @dns = Net::DNS::Resolver.new
    end

    def lookup(domain, type: :A)
      begin
        packet = @dns.query(domain, type)

        answers = packet.answer.map { |rr|
          {
            name: rr.name,
            type: rr.type,
            ttl: rr.ttl,
            value: rr.data.to_s
          }
        }

        {
          domain: domain,
          query_type: type.to_s,
          success: true,
          answers: answers,
          timestamp: Time.now.iso8601
        }
      rescue => e
        {
          domain: domain,
          success: false,
          error: e.message,
          timestamp: Time.now.iso8601
        }
      end
    end

    def reverse_lookup(ip)
      begin
        result = @dns.getname(ip)
        {
          ip: ip,
          hostname: result,
          timestamp: Time.now.iso8601
        }
      rescue => e
        {
          ip: ip,
          error: e.message,
          timestamp: Time.now.iso8601
        }
      end
    end

    def whois(domain)
      begin
        response = HTTParty.get(
          "https://whois.arin.net/rest/ip/#{domain}",
          headers: { "Accept" => "application/json" },
          timeout: 10
        )

        if response.success?
          {
            domain: domain,
            success: true,
            data: JSON.parse(response.body),
            timestamp: Time.now.iso8601
          }
        else
          {
            domain: domain,
            success: false,
            error: "WHOIS lookup failed",
            timestamp: Time.now.iso8601
          }
        end
      rescue => e
        {
          domain: domain,
          success: false,
          error: e.message,
          timestamp: Time.now.iso8601
        }
      end
    end

    def mx_records(domain)
      lookup(domain, type: :MX)
    end

    def ns_records(domain)
      lookup(domain, type: :NS)
    end

    def soa_record(domain)
      lookup(domain, type: :SOA)
    end

    def find_subdomains(domain, wordlist: nil)
      wordlist ||= ["www", "mail", "ftp", "admin", "api", "dev", "test", "staging"]

      subdomains = []

      wordlist.each do |word|
        subdomain = "#{word}.#{domain}"
        begin
          result = lookup(subdomain)
          if result[:success] && result[:answers].any?
            subdomains << subdomain
          end
        rescue
          # Skip failed lookups
        end
      end

      {
        domain: domain,
        subdomains: subdomains,
        count: subdomains.length,
        timestamp: Time.now.iso8601
      }
    end
  end
end

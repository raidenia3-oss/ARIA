#!/usr/bin/env ruby
# AURA Personal Assistant CLI - Ruby Edition
# Interfaz de chat con AURA Backend

require 'net/http'
require 'json'
require 'uri'

API_URL = 'http://localhost:8000/api/chat'
VERSION = '1.0'

def clear
  system('clear') || system('cls')
end

def print_banner
  clear
  puts "╔════════════════════════════════════════════════════════════════╗"
  puts "║                                                                ║"
  puts "║     🤖 AURA Personal Assistant v#{VERSION} (Ruby Edition)        ║"
  puts "║                                                                ║"
  puts "║         Backend: http://localhost:8000                        ║"
  puts "║         Type 'exit' to quit                                   ║"
  puts "║                                                                ║"
  puts "╚════════════════════════════════════════════════════════════════╝"
  puts ""
end

def send_message(message)
  uri = URI(API_URL)
  req = Net::HTTP::Post.new(uri, 'Content-Type' => 'application/json')
  req.body = { message: message }.to_json
  
  res = Net::HTTP.start(uri.hostname, uri.port, read_timeout: 30) do |http|
    http.request(req)
  end
  
  JSON.parse(res.body)
rescue => e
  { 'error' => e.message }
end

def main
  print_banner
  
  loop do
    print "You: "
    input = STDIN.gets&.chomp
    
    break if input.nil? || input == 'exit'
    next if input.strip.empty?
    
    puts "AURA: Thinking..."
    
    response = send_message(input)
    
    if response['response']
      puts "AURA: #{response['response']}"
    elsif response['error']
      puts "AURA: ✗ Error: #{response['error']}"
    else
      puts "AURA: ✗ Error connecting to backend"
    end
    
    puts ""
  end
  
  puts ""
  puts "✓ AURA saying goodbye..."
  puts "Goodbye! See you next time."
end

main if __FILE__ == $0

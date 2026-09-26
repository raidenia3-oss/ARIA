#!/usr/bin/env ruby
# AURA OS — Hash & Encoding Utilities
# Usage: ruby hash_utils.rb [options]
#
# Examples:
#   ruby hash_utils.rb --hash sha256 "hello world"
#   ruby hash_utils.rb --encode base64 "hello world"
#   ruby hash_utils.rb --decode base64 "aGVsbG8gd29ybGQ="
#   ruby hash_utils.rb --compare "password123" "sha256:5e88..."

require 'digest'
require 'base64'
require 'cgi'
require 'optparse'
require 'pastel'

$pastel = Pastel.new

HASH_ALGORITHMS = %w[md5 sha1 sha256 sha384 sha512 sha3-256 sha3-512].freeze

def compute_hash(input, algorithm)
  algo = algorithm.downcase
  case algo
  when 'md5' then Digest::MD5.hexdigest(input)
  when 'sha1' then Digest::SHA1.hexdigest(input)
  when 'sha256' then Digest::SHA256.hexdigest(input)
  when 'sha384' then Digest::SHA384.hexdigest(input)
  when 'sha512' then Digest::SHA512.hexdigest(input)
  when 'sha3-256' then Digest::SHA3_256.hexdigest(input)
  when 'sha3-512' then Digest::SHA3_512.hexdigest(input)
  else
    raise "Unknown algorithm: #{algorithm}"
  end
end

def encode(input, encoding)
  case encoding
  when 'base64' then Base64.strict_encode64(input)
  when 'base64-url' then Base64.urlsafe_encode64(input)
  when 'hex' then input.bytes.map { |b| b.to_s(16).rjust(2, '0') }.join
  when 'url' then CGI.escape(input)
  when 'binary' then input.bytes.map { |b| b.to_s(2).rjust(8, '0') }.join(' ')
  else
    raise "Unknown encoding: #{encoding}"
  end
end

def decode(input, encoding)
  case encoding
  when 'base64' then Base64.strict_decode64(input)
  when 'base64-url' then Base64.urlsafe_decode64(input)
  when 'hex' then [input].pack('H*')
  when 'url' then CGI.unescape(input)
  when 'binary' then input.split.map { |b| b.to_i(2) }.pack('C*')
  else
    raise "Unknown encoding: #{encoding}"
  end
end

def generate_salt(length = 16)
  bytes = []
  length.times { bytes << rand(256) }
  bytes.pack('C*')
end

def hash_password(password, algorithm = 'sha256', salt: nil)
  salt ||= generate_salt(16)
  hash = compute_hash(salt + password, algorithm)
  return "#{algorithm}$#{Base64.strict_encode64(salt)}$#{hash}"
end

def verify_password(password, stored_hash)
  parts = stored_hash.split('$')
  return false if parts.size != 3

  algorithm, salt_b64, expected_hash = parts
  salt = Base64.strict_decode64(salt_b64)
  actual_hash = compute_hash(salt + password, algorithm)
  return actual_hash == expected_hash
end

options = {}
OptionParser.new do |opts|
  opts.banner = "Uso: ruby hash_utils.rb [opciones]"
  opts.on("--hash ALGO", "Hash algorithm (md5, sha1, sha256, sha512, sha3-256, sha3-512)") do |algo|
    options[:algo] = algo
  end
  opts.on("--encode FORMAT", "Encode format (base64, hex, url, binary)") do |format|
    options[:encode] = format
  end
  opts.on("--decode FORMAT", "Decode format (base64, hex, url, binary)") do |format|
    options[:decode] = format
  end
  opts.on("--password-hash", "Hash password with salt (sha256 default)") do
    options[:password] = true
  end
  opts.on("--password-verify HASH", "Verify password against stored hash") do |hash|
    options[:verify_hash] = hash
  end
  opts.on("--list-algorithms", "List supported hash algorithms") do
    options[:list] = true
  end
  opts.on("-h", "--help", "Mostrar ayuda") do
    puts opts
    exit
  end
end.parse!

if options[:list]
  puts $pastel.cyan("Hash algorithms:")
  HASH_ALGORITHMS.each { |a| puts "  #{a}" }
  puts
  puts $pastel.cyan("Encodings:")
  puts "  base64, base64-url, hex, url, binary"
  exit 0
end

input = ARGV.shift

if options[:algo]
  algo = options[:algo]
  input ||= ''
  begin
    result = compute_hash(input, algo)
    puts $pastel.cyan("#{algo.upcase}: #{result}")
    puts $pastel.dim("Length: #{result.length} chars")
  rescue => e
    puts $pastel.red("Error: #{e.message}")
  end
elsif options[:encode]
  format = options[:encode]
  input ||= ''
  begin
    result = encode(input, format)
    puts $pastel.cyan("#{format} encode: #{result}")
  rescue => e
    puts $pastel.red("Error: #{e.message}")
  end
elsif options[:decode]
  format = options[:decode]
  input ||= ''
  begin
    result = decode(input, format)
    puts $pastel.cyan("#{format} decode: #{result}")
  rescue => e
    puts $pastel.red("Error: #{e.message}")
  end
elsif options[:password]
  input ||= ''
  result = hash_password(input)
  puts $pastel.cyan("Hashed: #{result}")
elsif options[:verify_hash]
  input ||= ''
  hash = options[:verify_hash]
  if verify_password(input, hash)
    puts $pastel.green("Password matches!")
  else
    puts $pastel.red("Password does not match.")
  end
else
  puts "Uso: ruby hash_utils.rb [opciones]"
  puts "Usa --help para mas informacion."
end

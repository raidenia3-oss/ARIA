#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/hash_tools.rb

require 'digest'
require 'bcrypt'
require 'base64'
require 'uri'
require 'time'

module AuraTools
  class HashTools

    def self.md5(string)
      Digest::MD5.hexdigest(string)
    end

    def self.sha1(string)
      Digest::SHA1.hexdigest(string)
    end

    def self.sha256(string)
      Digest::SHA256.hexdigest(string)
    end

    def self.sha512(string)
      Digest::SHA512.hexdigest(string)
    end

    def self.bcrypt(password, cost: 12)
      BCrypt::Password.create(password, cost: cost)
    end

    def self.bcrypt_verify(password, hash)
      BCrypt::Password.new(hash) == password
    end

    def self.base64_encode(string)
      Base64.strict_encode64(string)
    end

    def self.base64_decode(encoded)
      Base64.strict_decode64(encoded)
    end

    def self.url_encode(string)
      URI.encode_www_form_component(string)
    end

    def self.url_decode(encoded)
      URI.decode_www_form_component(encoded)
    end

    def self.hex_encode(string)
      string.unpack('H*')[0]
    end

    def self.hex_decode(hex_string)
      [hex_string].pack('H*')
    end

    def self.identify_hash(hash_string)
      case hash_string.length
      when 32
        :md5
      when 40
        :sha1
      when 64
        :sha256
      when 128
        :sha512
      when 60
        :bcrypt
      else
        :unknown
      end
    end

    def self.secure_compare(a, b)
      Digest::SHA256.hexdigest(a) == Digest::SHA256.hexdigest(b)
    end
  end
end

#!/usr/bin/env ruby
# aura-os/ruby-tools/lib/aura_tools.rb

require 'json'
require 'time'
require_relative 'network_scanner'
require_relative 'dns_resolver'
require_relative 'hash_tools'
require_relative 'system_tools'
require_relative 'exploit_framework'
require_relative 'payload_generator'
require_relative 'red_team_tools'

module AuraTools
  VERSION = "2.0.0"

  class << self
    attr_accessor :config

    def configure
      @config ||= {}
      yield(@config) if block_given?
    end

    def version
      VERSION
    end
  end
end

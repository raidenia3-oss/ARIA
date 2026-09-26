require 'json'
require 'httparty'
require_relative '../bot'

RSpec.describe Aura::DiscordBot do
  describe '.new' do
    it 'initializes with config overrides' do
      allow(Redis).to receive(:new).and_return(instance_double(Redis))
      bot = described_class.new('DISCORD_BOT_TOKEN' => 'token', 'DISCORD_CLIENT_ID' => 'client', 'skip_registration' => true)
      expect(bot).to be_a(described_class)
    end
  end

  describe '#call_backend' do
    it 'returns parsed JSON on success' do
      allow(Redis).to receive(:new).and_return(instance_double(Redis))
      bot = described_class.new('DISCORD_BOT_TOKEN' => 'token', 'DISCORD_CLIENT_ID' => 'client', 'AURA_BACKEND_URL' => 'http://localhost:8000', 'skip_registration' => true)
      response = double('response', body: '{"status":"ok"}')
      allow(HTTParty).to receive(:get).and_return(response)

      result = bot.send(:call_backend, 'GET', 'http://localhost:8000/api/status')
      expect(result).to eq({ status: 'ok' })
    end

    it 'returns error hash on failure' do
      allow(Redis).to receive(:new).and_return(instance_double(Redis))
      bot = described_class.new('DISCORD_BOT_TOKEN' => 'token', 'DISCORD_CLIENT_ID' => 'client', 'AURA_BACKEND_URL' => 'http://localhost:8000', 'skip_registration' => true)
      allow(HTTParty).to receive(:get).and_raise(StandardError, 'connection failed')

      result = bot.send(:call_backend, 'GET', 'http://localhost:8000/api/status')
      expect(result).to eq({ error: 'connection failed' })
    end
  end

  describe '#generate_esoteric_challenge' do
    it 'returns brainfuck challenge by default' do
      allow(Redis).to receive(:new).and_return(instance_double(Redis))
      bot = described_class.new('DISCORD_BOT_TOKEN' => 'token', 'DISCORD_CLIENT_ID' => 'client', 'skip_registration' => true)
      challenge = bot.send(:generate_esoteric_challenge, 'brainfuck')
      expect(challenge).to include('brainfuck')
    end
  end
end

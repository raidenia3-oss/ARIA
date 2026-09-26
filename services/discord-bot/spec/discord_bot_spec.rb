require_relative '../bot'

RSpec.describe Aura::DiscordBot do
  describe '.new' do
    it 'initializes with config overrides' do
      allow(Redis).to receive(:new).and_return(instance_double(Redis))
      bot = described_class.new('DISCORD_BOT_TOKEN' => 'token', 'DISCORD_CLIENT_ID' => 'client', 'skip_registration' => true)
      expect(bot).to be_a(described_class)
    end
  end
end

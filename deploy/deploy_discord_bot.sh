#!/usr/bin/env bash
set -e

echo "Deploying AURA Discord Bot..."

if [ -z "$DISCORD_BOT_TOKEN" ]; then
  echo "ERROR: DISCORD_BOT_TOKEN is required"
  exit 1
fi

if [ -z "$DISCORD_CLIENT_ID" ]; then
  echo "ERROR: DISCORD_CLIENT_ID is required"
  exit 1
fi

if [ -z "$AURA_BACKEND_URL" ]; then
  echo "ERROR: AURA_BACKEND_URL is required"
  exit 1
fi

bundle install --gemfile services/discord-bot/Gemfile
bundle exec --gemfile services/discord-bot/Gemfile ruby services/discord-bot/bot.rb

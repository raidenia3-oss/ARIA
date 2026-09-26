#!/usr/bin/env ruby
# frozen_string_literal: true

# AURA Discord Bot — Multi-language expansion
# Stack: Ruby 3.3 + discordrb + Redis + dotenv
# Commands: /status, /logs, /restart, /deploy, /esoteric, /rules, /story

require 'cgi'
require 'discordrb'
require 'fileutils'
require 'json'
require 'uri'
require 'net/http'
require 'tmpdir'
require 'base64'

begin
  require 'dotenv'
  Dotenv.load(
    File.expand_path('.env', __dir__),
    File.expand_path('.env.local', __dir__)
  )
rescue LoadError
  nil
end

require 'httparty'
require 'redis'

require_relative '../dsl-compiler/lib/dsl_compiler'

module Aura
  class DiscordBot
    COMMANDS_LAST_SYNC_FILE = File.expand_path('.commands_synced', __dir__)
    COMMANDS_SYNC_COOLDOWN = 3600

    def initialize(config = {})
      @skip_registration = config.delete('skip_registration')
      @skip_command_registration = config.delete('skip_command_registration')
      @token = config.fetch('DISCORD_BOT_TOKEN') { ENV['DISCORD_BOT_TOKEN'] }
      @client_id = config.fetch('DISCORD_CLIENT_ID') { ENV['DISCORD_CLIENT_ID'] }
      @guild_id = config.fetch('DISCORD_GUILD_ID') { ENV['DISCORD_GUILD_ID'] }
      @ops_channel = config.fetch('DISCORD_NOTIFY_CHANNEL') { ENV.fetch('DISCORD_NOTIFY_CHANNEL', 'ops') }
      @backend_url = config.fetch('AURA_BACKEND_URL') { ENV.fetch('AURA_BACKEND_URL', 'http://localhost:8000') }
      @redis = Redis.new(url: config.fetch('REDIS_URL') { ENV.fetch('REDIS_URL', 'redis://localhost:6379/0') })
      @canon_feed_channel = config.fetch('DISCORD_CANON_FEED_CHANNEL') { ENV['DISCORD_CANON_FEED_CHANNEL'] }
      @watched_works = []
      @seen_canon = []
      @canon_mutex = Mutex.new
      @stt_calls = []
      @stt_mutex = Mutex.new

      @bot = if @skip_registration || @token.to_s.strip.empty? || @client_id.to_s.strip.empty?
               nil
             else
               Discordrb::Bot.new(token: @token, client_id: @client_id)
             end

      unless @skip_registration || @bot.nil?
        register_commands
        register_events
      end
    end

    def start
      return puts '[AURA DiscordBot] Missing credentials; skipping startup.' if @bot.nil?

      puts '[AURA DiscordBot] Connecting...'
      record_connection_status("connecting")
      @bot.run
      record_connection_status("disconnected")
    rescue StandardError => e
      warn "[AURA DiscordBot] Connection stopped: #{e.class}: #{e.message}"
      record_connection_status("error: #{e.class}")
      raise
    end

    private

    def commands_already_synced?
      return false unless File.exist?(COMMANDS_LAST_SYNC_FILE)
      last_sync = File.read(COMMANDS_LAST_SYNC_FILE).to_i
      (Time.now.to_i - last_sync) < COMMANDS_SYNC_COOLDOWN
    rescue StandardError
      false
    end

    def mark_commands_synced
      File.write(COMMANDS_LAST_SYNC_FILE, Time.now.to_i.to_s)
    rescue StandardError
      nil
    end

    def record_connection_status(status)
      return unless @backend_url
      Thread.new do
        begin
          uri = URI("#{@backend_url}/api/discord/connection-status")
          req = Net::HTTP::Post.new(uri)
          req["Content-Type"] = "application/json"
          req.body = { status: status }.to_json
          Net::HTTP.start(uri.host, uri.port, read_timeout: 3, open_timeout: 3) do |http|
            http.request(req)
          end
        rescue StandardError
          nil
        end
      end
    rescue StandardError
      nil
    end

    def register_commands
      if @skip_command_registration
        puts '[AURA DiscordBot] Skipping command registration (skip_command_registration).'
      elsif commands_already_synced?
        puts '[AURA DiscordBot] Commands already synced recently; skipping registration.'
      else
        register_command(:status, 'Show AURA services status') do |cmd|
        cmd.string(:service, 'Service name', required: false)
      end

      register_command(:logs, 'Get recent logs from a service') do |cmd|
        cmd.string(:service, 'Service name', required: true)
        cmd.integer(:lines, 'Number of lines', required: false)
      end

      register_command(:restart, 'Restart an AURA service') do |cmd|
        cmd.string(:service, 'Service name', required: true)
      end

      register_command(:deploy, 'Deploy an AURA service') do |cmd|
        cmd.string(:service, 'Service to deploy', required: true, choices: { 'HF Space' => 'hf-space', 'Backend' => 'backend', 'Frontend' => 'frontend' })
      end

      register_command(:esoteric, 'Generate esoteric code challenge') do |cmd|
        cmd.string(:language, 'Esoteric language', required: false, choices: { 'brainfuck' => 'brainfuck', 'LOLCODE' => 'lolcode', 'Whitespace' => 'whitespace', 'Malbolge' => 'malbolge' })
      end

      register_command(:rules, 'List or evaluate automation rules') do |cmd|
        cmd.string(:action, 'Action', required: true, choices: { 'list' => 'list', 'evaluate' => 'evaluate' })
        cmd.string(:rule_name, 'Rule name', required: false)
      end

      register_command(:chat, 'Chat with AURA') do |cmd|
        cmd.string(:prompt, 'Your message', required: true)
      end

      register_command(:feedback, 'Send feedback for AURA responses') do |cmd|
        cmd.string(:value, 'Feedback: up or down', required: true, choices: { '👍 Up' => 'up', '👎 Down' => 'down' })
      end

      register_command(:story, 'Manage literary context (base literaria)') do |cmd|
        cmd.string(:action, 'Action', required: true, choices: {
          'Estado' => 'status',
          'Establecer obra' => 'set-work',
          'Establecer personaje' => 'set-character',
          'Validar coherencia' => 'check-coherence',
          'Invocar personaje' => 'persona',
          'Ver canon' => 'canon',
          'Desvincular' => 'unbind'
        })
        cmd.string(:work, 'Work ID', required: false)
        cmd.string(:character, 'Character ID', required: false)
        cmd.string(:text, 'Text to validate coherence', required: false)
      end

      register_command(:vault, 'Bóveda de archivos en Discord (storage local)') do |cmd|
        cmd.string(:action, 'Action', required: true, choices: {
          'Listar' => 'list',
          'Buscar' => 'search',
          'Estadísticas' => 'stats'
        })
        cmd.string(:query, 'Query for search', required: false)
      end

      register_command(:backup, 'Respaldar base literaria a Discord Vault') do |cmd|
        cmd.string(:action, 'Action', required: true, choices: { 'Story' => 'story', 'Sessions' => 'sessions', 'Todo' => 'all' })
      end

      @bot.application_command(:status) do |event|
        event.respond(content: build_command_response('status', event.options || {}))
      end

      @bot.application_command(:logs) do |event|
        event.respond(content: build_command_response('logs', event.options || {}))
      end

      @bot.application_command(:restart) do |event|
        event.respond(content: build_command_response('restart', event.options || {}))
      end

      @bot.application_command(:deploy) do |event|
        event.respond(content: build_command_response('deploy', event.options || {}))
      end

      @bot.application_command(:esoteric) do |event|
        event.respond(content: build_command_response('esoteric', event.options || {}))
      end

      @bot.application_command(:rules) do |event|
        event.respond(content: build_command_response('rules', event.options || {}))
      end

      @bot.application_command(:chat) do |event|
        prompt = event.options['prompt'] || event.options[:prompt]
        event.respond(content: build_chat_response(prompt))
      end

      @bot.application_command(:feedback) do |event|
        value = event.options['value'] || event.options[:value]
        event.respond(content: build_feedback_response(value))
      end

      @bot.application_command(:story) do |event|
        action = event.options['action'] || event.options[:action]
        work = event.options['work'] || event.options[:work]
        character = event.options['character'] || event.options[:character]
        text = event.options['text'] || event.options[:text] || event.options['prompt']
        event.respond(content: build_story_response(event, action, work, character, text))
      end

      @bot.application_command(:vault) do |event|
        action = event.options['action'] || event.options[:action]
        query = event.options['query'] || event.options[:query]
        event.respond(content: build_vault_response(action, query))
      end

      @bot.application_command(:backup) do |event|
        action = event.options['action'] || event.options[:action] || 'all'
        event.respond(content: build_backup_response(event, action))
      end

      mark_commands_synced
      end
    end

    def register_command(name, description, &block)
      @bot.register_application_command(name, description, &block)
    end

    def register_events
      @bot.ready do
        begin
          puts "[AURA DiscordBot] Ready as #{@bot.profile.username}"
          record_connection_status("connected")
          ops_channel = notification_channel
          if ops_channel
            ops_channel.send_message("🟢 AURA DiscordBot online — #{Time.now.strftime('%Y-%m-%d %H:%M:%S')}")
          end
          start_canon_feed_poller
        rescue StandardError => e
          warn "[AURA DiscordBot] Error in ready handler: #{e.class}: #{e.message}"
        end
      end

      @bot.disconnected do
        warn '[AURA DiscordBot] Disconnected from Discord; the process manager should restart it.'
        record_connection_status("disconnected")
      end

      @bot.message do |event|
        next if event.author.bot_account?

        audio_attachment = first_voice_attachment(event)
        if audio_attachment
          # Procesar en hilo aparte: descarga + STT local no deben bloquear el event loop.
          Thread.new do
            handle_voice_to_canon(event, audio_attachment)
          rescue StandardError => e
            warn "[AURA DiscordBot] voice-to-canon error: #{e.class}: #{e.message}"
          end
          next
        end

        # Auto-indexar adjuntos en el canal bóveda (Discord como storage local).
        index_vault_attachment(event)

        publish_event(
          type: 'message',
          user: event.author.id,
          channel: event.channel.id,
          content: event.content,
          timestamp: Time.now.to_i
        )
      end

      @bot.voice_state_update do |event|
        publish_event(
          type: 'voice_state',
          user: event.user.id,
          channel: event.channel&.id,
          action: event.old_channel ? 'leave' : 'join',
          timestamp: Time.now.to_i
        )
      end
    end

    def notification_channel
      channel_id = Integer(@ops_channel, 10)
      @bot.channel(channel_id)
    rescue ArgumentError, TypeError
      @bot.servers.values
          .flat_map(&:channels)
          .find { |channel| channel.name == @ops_channel }
    rescue StandardError
      nil
    end

    def publish_event(payload)
      @redis.rpush('aura:events', payload.to_json)
    rescue Redis::BaseError => e
      warn "[AURA DiscordBot] Redis unavailable; event not queued: #{e.message}"
    end

    def story_session_id(event)
      return '' unless event
      user_id = event.user&.id
      "discord_#{user_id}"
    end

    def build_story_response(event, action, work, character, text)
      session_id = story_session_id(event)
      if session_id.empty?
        return 'No se pudo determinar la sesión de Discord.'
      end

      case action
      when 'set-work'
        set_story_work(session_id, work, character)
      when 'set-character'
        set_story_character(session_id, character)
      when 'check-coherence'
        check_story_coherence(session_id, work, character, text)
      when 'persona'
        invoke_character_persona(session_id, work, character, text)
      when 'canon'
        list_canon_events(session_id, work)
      when 'unbind'
        clear_story_context(session_id)
      else
        story_status(session_id)
      end
    rescue StandardError => e
      "Error de contexto literario: #{e.message}"
    end

    def story_error(response)
      return nil unless response.is_a?(Hash)
      response[:error] || response[:detail] || response['error'] || response['detail']
    end

    def story_status(session_id)
      response = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      err = story_error(response)
      return err if err
      if response['active'] || response[:active]
        ctx = response['context'] || response[:context]
        ctx = ctx || {}
        "🟢 Contexto: obra `#{ctx['work_id'] || ctx[:work_id]}`, personaje `#{ctx['character_id'] || ctx[:character_id]}`"
      else
        '⚪ Sin contexto literario vinculado. Usa `/story set-work` con una obra.'
      end
    end

    def set_story_work(session_id, work, character)
      return 'Falta el parámetro `work` (ID de obra).' if work.nil? || work.to_s.strip.empty?
      work = work.to_s.strip

      if character.nil? || character.to_s.strip.empty?
        chars = list_work_characters(work)
        if chars.empty?
          return "La obra `#{work}` no tiene personajes. Crea uno en la base literaria primero."
        end
        character = chars.first
      end

      bind_story(session_id, work, character)
    end

    def set_story_character(session_id, character)
      return 'Falta el parámetro `character` (ID de personaje).' if character.nil? || character.to_s.strip.empty?
      current = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      err = story_error(current)
      return err if err
      work = (current['context'] || current[:context] || {}).fetch('work_id', nil) if current['active'] || current[:active]
      work ||= (current['work_id'] || current[:work_id])
      return 'No hay obra activa. Establece primero una obra con `/story set-work`.' if work.nil() || work.to_s.empty?

      bind_story(session_id, work, character.to_s.strip)
    end

    def bind_story(session_id, work, character)
      watch_work(work)
      response = call_backend('POST', build_backend_path("/api/story/sessions/#{session_id}/context"), {
                                work_id: work,
                                character_id: character
                              })
      err = story_error(response)
      return err if err
      if response['status'] == 'bound' || response[:status] == 'bound'
        "✅ Contexto vinculado: obra `#{work}` / personaje `#{character}`"
      else
        "No se pudo vincular: #{response.inspect}"
      end
    end

    def clear_story_context(session_id)
      response = call_backend('DELETE', build_backend_path("/api/story/sessions/#{session_id}/context"))
      err = story_error(response)
      return err if err
      if response['cleared'] || response[:cleared]
        '✅ Contexto literario desvinculado.'
      else
        'La sesión no tenía contexto vinculado.'
      end
    end

    def check_story_coherence(session_id, work, character, text)
      return 'Falta el parámetro `text` para validar coherencia.' if text.nil() || text.to_s.strip.empty?
      current = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      ctx = {}
      if current.is_a?(Hash) && !story_error(current) && (current['active'] || current[:active])
        ctx = current['context'] || current[:context] || {}
      end
      work = work.to_s.strip.empty? ? (ctx['work_id'] || ctx[:work_id]) : work.to_s.strip
      character = character.to_s.strip.empty? ? (ctx['character_id'] || ctx[:character_id]) : character.to_s.strip
      if work.nil() || work.to_s.empty? || character.nil() || character.to_s.empty?
        return 'Faltan obra y personaje activos. Vincula contexto o pasa `work` y `character`.'
      end

      response = call_backend('POST', build_backend_path("/api/story/#{work}/check-consistency"), {
                                char_id: character,
                                text: text.to_s
                              })
      err = story_error(response)
      return err if err
      if response['overall_pass'] || response[:overall_pass]
        classif = response['source_classification'] || response[:source_classification] || {}
        "✅ Coherente — fuente: #{classif['classification'] || classif[:classification] || 'desconocida'}"
      else
        violations = response['character_consistency'] || response[:character_consistency] || {}
        vios = violations['violations'] || violations[:violations] || []
        details = vios.map { |v| "- #{v['description'] || v[:description] || v['type'] || v[:type]}" }.join("\n")
        "🚨 Incoherente.\n#{details.empty? ? 'No se detectaron detalles.' : details}"
      end
    end

    def list_work_characters(work)
      response = call_backend('GET', build_backend_path("/api/story/#{work}/characters"))
      return [] if story_error(response)
      chars = response['characters'] || response[:characters] || []
      chars.map { |c| c['char_id'] || c[:char_id] || c['name'] || c[:name] }
    end

    def invoke_character_persona(session_id, work, character, prompt)
      return 'Falta el parámetro `character` (ID de personaje).' if character.nil? || character.to_s.strip.empty?
      return 'Falta el `prompt` (texto a enviar al personaje).' if prompt.nil? || prompt.to_s.strip.empty?

      current = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      work = work.to_s.strip unless work && !work.to_s.strip.empty?
      character = character.to_s.strip

      char_data = nil
      if work && !work.to_s.strip.empty?
        chars_resp = call_backend('GET', build_backend_path("/api/story/#{work}/characters"))
        if !story_error(chars_resp)
          chars = chars_resp['characters'] || chars_resp[:characters] || []
          char_data = chars.find { |c|
            (c['char_id'] || c[:char_id]) == character ||
            (c['name'] || c[:name]) == character
          }
          character = (char_data['char_id'] || char_data[:char_id]) if char_data
        end
      end

      context = if current['context']
        "Obra: #{current['context']['work_id']}, Personaje: #{current['context']['character_id']}"
      else
        "No hay contexto vinculado"
      end

      voice = char_data ? (char_data['voice'] || char_data[:voice] || 'voz neutral') : 'voz neutral'
      personality = char_data ? ((char_data['personality'] || char_data[:personality] || []).join(', ')) : 'personalidad desconocida'

      response = call_backend('POST', build_backend_path('/api/chat'), {
        prompt: prompt,
        session_id: session_id,
        router: true,
      })

      if story_error(response)
        "Error al invocar al personaje: #{story_error(response)}"
      else
        reply = response[:reply] || response['reply'] || response[:text] || response['text'] || '(sin respuesta)'
        "**[#{char_data ? (char_data['name'] || char_data[:name] || character) : character}]** «#{voice}»\n*#{personality}*\n\n*Contexto: #{context}*\n\n#{reply}"
      end
    end

    def list_canon_events(session_id, work)
      current = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      work = work.to_s.strip if work && !work.to_s.strip.empty?

      unless work && !work.to_s.strip.empty?
        if current.is_a?(Hash) && !story_error(current)
          ctx = current['context'] || current[:context]
          work = ctx && (ctx['work_id'] || ctx[:work_id])
        end
      end

      unless work && !work.to_s.strip.empty?
        return 'Sin obra activa. Usa `/story set-work` primero.'
      end

      response = call_backend('GET', build_backend_path("/api/story/#{work}/canon"))
      if story_error(response)
        "Error al consultar canon: #{story_error(response)}"
      else
        events = response['events'] || response[:events] || []
        if events.empty?
          '📜 El canon de esta obra está vacío.'
        else
          lines = events.map.with_index(1) { |e, i|
            timestamp = Time.at(e['timestamp'] || e[:timestamp] || Time.now.to_i).strftime('%Y-%m-%d %H:%M')
            "##{i}. [#{timestamp}] #{e['description'] || e[:description]} (source: #{e['source'] || e[:source] || 'desconocido'})"
          }
          "📜 **Canon de la obra `#{work}`** (#{events.length} eventos):\n#{lines.join("\n")}"
        end
      end
    end

    def voice_to_canon(session_id, work, audio_url, transcription = nil)
      return 'No hay obra vinculada para el canon.' if work.nil? || work.to_s.strip.empty?
      work = work.to_s.strip

      # BLOQUE 37: STT local primero (Faster-Whisper en el backend AURA);
      # si no está disponible, fallback a la simulación previa.
      transcript = transcription || local_transcription(audio_url) || simulate_transcription(audio_url)
      return "No se pudo transcribir el audio." if transcript.nil? || transcript.strip.empty?

      timestamp = Time.now.to_f
      response = call_backend('POST', build_backend_path("/api/story/#{work}/canon"), {
        description: transcript,
        timestamp: timestamp,
        scene_ref: "discord_voice:#{session_id}",
        source: "discord_voice",
      })

      if story_error(response)
        "Error al registrar canon: #{story_error(response)}"
      else
        event_id = response['event_id'] || response[:event_id] || 'desconocido'
        publish_canon_feed(work, event_id, transcript, session_id)
        "🎙️→📜 Voz convertida a canon (#{event_id}): \"#{transcript[0..100]}#{transcript.length > 100 ? '...' : ''}\""
      end
    end

    def simulate_transcription(audio_url)
      # Fallback: solo se usa si el STT local (Bloque 37) no está disponible.
      "[transcripción simulada] Mensaje de voz registrado desde Discord. URL: #{audio_url}"
    end

    # BLOQUE 37 — Discord Voice-Note Bridge hacia el motor STT local.
    # Descarga el adjunto de audio y lo envía a /api/audio/transcribe del
    # backend AURA (Faster-Whisper local). Retorna nil ante cualquier fallo
    # para que el flujo caiga al fallback simulado sin romper el bot.
    def local_transcription(audio_url)
      return nil unless @backend_url && audio_url

      uri = URI.parse(audio_url)
      audio = Net::HTTP.get(uri)
      return nil if audio.nil? || audio.empty?

      filename = File.basename(uri.path).empty? ? 'voice.ogg' : File.basename(uri.path)
      endpoint = URI.join(@backend_url, '/api/audio/transcribe')
      req = Net::HTTP::Post.new(endpoint)
      req['X-API-Key'] = ENV['AURA_API_KEY'] if ENV['AURA_API_KEY']
      req.set_form(
        [['file', audio, { filename: filename }]],
        'multipart/form-data'
      )
      http = Net::HTTP.new(endpoint.host, endpoint.port)
      http.use_ssl = endpoint.scheme == 'https'
      http.open_timeout = 5
      http.read_timeout = 120
      resp = http.request(req)
      return nil unless resp.is_a?(Net::HTTPSuccess)

      body = JSON.parse(resp.body)
      text = body['text'].to_s.strip
      text.empty? ? nil : text
    rescue StandardError => e
      warn "[AURA DiscordBot] STT local no disponible (#{e.class}: #{e.message}); usando fallback"
      nil
    end

    def publish_canon_feed(work, event_id, description, session_id)
      return unless @backend_url

      Thread.new do
        begin
          timestamp = Time.now.to_i
          event = {
            title: "Nuevo evento de canon",
            work_id: work,
            event_id: event_id,
            description: description,
            source: "discord_voice",
            session_id: session_id,
            timestamp: timestamp,
          }

          payload = {
            content: "📜 **Canon Feed**",
            embeds: [
              {
                title: event[:title],
                color: 0x5865F2,
                fields: [
                  { name: "Obra", value: event[:work_id], inline: true },
                  { name: "Evento", value: event[:event_id], inline: true },
                  { name: "Fuente", value: event[:source], inline: true },
                  { name: "Descripción", value: event[:description][0..1024] },
                ],
                timestamp: Time.at(event[:timestamp]).utc.isoformat,
              },
            ],
          }

          uri = URI("#{@backend_url}/api/discord/canon-feed")
          req = Net::HTTP::Post.new(uri)
          req["Content-Type"] = "application/json"
          req["X-API-Key"] = ENV['AURA_API_KEY'] if ENV['AURA_API_KEY'] && !ENV['AURA_API_KEY'].empty?
          req.body = payload.to_json
          Net::HTTP.start(uri.host, uri.port, read_timeout: 3, open_timeout: 3) do |http|
            http.request(req)
          end
        rescue StandardError => e
          warn "[AURA DiscordBot] Canon feed publish failed: #{e.class}: #{e.message}"
        end
      end
    end

    def first_voice_attachment(event)
      return nil unless event.message.respond_to?(:attachments)
      audio_exts = ['.ogg', '.mp3', '.wav', '.m4a', '.webm']
      event.message.attachments.find do |att|
        ext = File.extname(att.url.to_s).downcase
        audio_exts.include?(ext) && att.size && att.size > 0
      end
    rescue StandardError
      nil
    end

    def handle_voice_to_canon(event, attachment)
      session_id = story_session_id(event)
      return if session_id.empty?

      current = call_backend('GET', build_backend_path("/api/story/sessions/#{session_id}/context"))
      work = nil
      if current.is_a?(Hash) && !story_error(current) && (current['active'] || current[:active])
        ctx = current['context'] || current[:context]
        work = ctx && (ctx['work_id'] || ctx[:work_id])
      end

      unless work && !work.to_s.strip.empty?
        event.channel.send_message("🔇 No hay obra vinculada. Vincula una obra con `/story set-work` antes de enviar notas de voz.")
        return
      end

      # Descarga temporal segura del archivo de audio
      audio_url = attachment.url
      tmp_dir = File.join(Dir.tmpdir, "aura_voice_#{Time.now.to_i}")
      FileUtils.mkdir_p(tmp_dir) unless File.directory?(tmp_dir)

      begin
        downloaded_path = download_voice_attachment(audio_url, tmp_dir)
        event.channel.send_message("🔄 Procesando nota de voz... (transcribiendo localmente)")

        # STT local real (whisper en backend) con fallback a simulación.
        transcription = real_transcription(downloaded_path) ||
                        simulate_transcription(audio_url)
        result = voice_to_canon(session_id, work, audio_url, transcription)
        event.channel.send_message(result)
      ensure
        FileUtils.rm_rf(tmp_dir) if File.directory?(tmp_dir)
      end
    rescue StandardError => e
      warn "[AURA DiscordBot] voice_to_canon handler error: #{e.class}: #{e.message}"
      event.channel&.send_message("❌ Error procesando nota de voz: #{e.message}")
    end

    def download_voice_attachment(url, dest_dir)
      require 'open-uri'
      ext = File.extname(URI.parse(url).path).downcase
      ext = '.ogg' unless ['.ogg', '.mp3', '.wav', '.m4a', '.webm'].include?(ext)
      filename = "voice_#{Time.now.to_i}#{ext}"
      path = File.join(dest_dir, filename)
      URI.open(url) { |io| FileUtils.cp(io.path, path) }
      path
    end

    def watch_work(work)
      return if work.nil? || work.to_s.strip.empty?
      @canon_mutex.synchronize do
        w = work.to_s.strip
        @watched_works << w unless @watched_works.include?(w)
      end
      seed_seen_canon(work)
    rescue StandardError
      nil
    end

    # Canon Feed automático: publica en el canal dedicado los eventos de canon
    # nuevos que aparezcan en el backend (creados por web, móvil u otro agente),
    # evitando duplicados y respetando el rate limit (poll cada CANON_POLL_INTERVAL).
    CANON_POLL_INTERVAL = 120
    CANON_SEED_LIMIT = 50

    def start_canon_feed_poller
      return if @canon_poller&.alive?
      @canon_poller = Thread.new do
        loop do
          sleep CANON_POLL_INTERVAL
          poll_canon_feeds
        end
      rescue StandardError => e
        warn "[AURA DiscordBot] Canon feed poller stopped: #{e.class}: #{e.message}"
      end
      warn "[AURA DiscordBot] Canon feed poller started (interval #{CANON_POLL_INTERVAL}s)"
    end

    def poll_canon_feeds
      works = @canon_mutex.synchronize { @watched_works.dup }
      works.each do |work|
        response = call_backend('GET', build_backend_path("/api/story/#{work}/canon"))
        next if story_error(response)
        events = response['events'] || response[:events] || []
        new_events = @canon_mutex.synchronize do
          fresh = events.reject { |e| @seen_canon.include?(e['event_id'] || e[:event_id]) }
          ids = events.map { |e| e['event_id'] || e[:event_id] }.compact
          @seen_canon.concat(ids)
          @seen_canon = @seen_canon.last(CANON_SEED_LIMIT * 4).uniq
          fresh
        end
        new_events.each { |e| publish_canon_embed(work, e) }
      end
    rescue StandardError => e
      warn "[AURA DiscordBot] Canon feed poll error: #{e.class}: #{e.message}"
    end

    def seed_seen_canon(work)
      response = call_backend('GET', build_backend_path("/api/story/#{work}/canon"))
      return if story_error(response)
      events = response['events'] || response[:events] || []
      ids = events.map { |e| e['event_id'] || e[:event_id] }.compact
      @canon_mutex.synchronize do
        @seen_canon.concat(ids)
        @seen_canon = @seen_canon.uniq.last(CANON_SEED_LIMIT * 4)
      end
    rescue StandardError
      nil
    end

    def publish_canon_embed(work, event)
      channel = canon_feed_channel
      return unless channel
      eid = event['event_id'] || event[:event_id] || '?'
      desc = (event['description'] || event[:description] || '').to_s
      src = (event['source'] || event[:source] || 'desconocido').to_s
      ts = event['timestamp'] || event[:timestamp] || Time.now.to_i
      channel.send_embed do |embed|
        embed.title = "📜 Canon Feed — `#{work}`"
        embed.colour = 0x5865F2
        embed.add_field(name: 'Evento', value: eid.to_s[0..254], inline: true)
        embed.add_field(name: 'Fuente', value: src[0..254], inline: true)
        embed.add_field(name: 'Descripción', value: desc[0..1023].empty? ? '—' : desc[0..1023])
        embed.timestamp = Time.at(ts.to_f)
      end
    rescue StandardError => e
      warn "[AURA DiscordBot] canon embed failed: #{e.class}: #{e.message}"
    end

    def canon_feed_channel
      return nil if @bot.nil?
      feed = @canon_feed_channel.to_s.strip
      target = feed.empty? ? @ops_channel : feed
      return nil if target.nil? || target.to_s.strip.empty?
      channel_id = Integer(target, 10)
      @bot.channel(channel_id)
    rescue ArgumentError, TypeError
      @bot.servers.values.flat_map(&:channels).find { |c| c.name == target }
    rescue StandardError
      nil
    end

    # Transcripción local vía backend (/api/voice/transcribe, whisper base).
    # Rate limit backend: 20/min → throttle cliente a 15/min. Fallback a simulación.
    STT_MAX_CALLS = 15
    STT_WINDOW_SECONDS = 60
    STT_MAX_BYTES = 24 * 1024 * 1024

    def stt_throttle_ok?
      now = Time.now.to_i
      @stt_mutex.synchronize do
        @stt_calls.reject! { |t| now - t >= STT_WINDOW_SECONDS }
        return false if @stt_calls.size >= STT_MAX_CALLS
        @stt_calls << now
        true
      end
    end

    def real_transcription(audio_path)
      return nil unless stt_throttle_ok?
      return nil unless File.exist?(audio_path)
      return nil if File.size(audio_path) > STT_MAX_BYTES

      encoded = Base64.strict_encode64(File.binread(audio_path))
      response = call_backend('POST', build_backend_path('/api/voice/transcribe'), {
                                audio_base64: encoded
                              })
      return nil if story_error(response)
      text = response['text'] || response[:text]
      text.nil? || text.strip.empty? ? nil : text.strip
    rescue StandardError
      nil
    end

    # -- Discord Storage Vault -------------------------------------------------
    VAULT_INDEX_FILE = File.expand_path('../../data/discord_vault_index.json', __dir__)
    VAULT_CHANNEL = ENV.fetch('DISCORD_VAULT_CHANNEL', '').strip

    def vault_index_path
      VAULT_INDEX_FILE
    end

    def load_vault_index
      return [] unless File.exist?(vault_index_path)
      data = JSON.parse(File.read(vault_index_path))
      data.is_a?(Array) ? data : []
    rescue StandardError
      []
    end

    def save_vault_index(entries)
      File.write(vault_index_path, JSON.pretty_generate(entries))
    rescue StandardError => e
      warn "[AURA DiscordBot] vault index save failed: #{e.class}: #{e.message}"
    end

    def index_vault_attachment(event)
      return if VAULT_CHANNEL.nil? || VAULT_CHANNEL.empty?
      return unless event.channel&.id&.to_s == VAULT_CHANNEL
      attachments = event.message.respond_to?(:attachments) ? event.message.attachments : []
      return if attachments.empty?

      entries = load_vault_index
      attachments.each do |att|
        entries << {
          'filename' => att.filename.to_s,
          'url' => att.url.to_s,
          'size' => att.size.to_i,
          'content_type' => att.content_type.to_s,
          'uploader' => event.author&.name.to_s,
          'message_id' => event.message&.id&.to_s,
          'channel_id' => event.channel&.id&.to_s,
          'timestamp' => Time.now.to_i,
        }
      end
      # Mantener sólo las últimas 500 entradas para no inflar el índice.
      entries = entries.last(500) if entries.length > 500
      save_vault_index(entries)
    rescue StandardError => e
      warn "[AURA DiscordBot] vault index failed: #{e.class}: #{e.message}"
    end

    def build_vault_response(action, query)
      entries = load_vault_index
      case action
      when 'search'
        q = (query || '').to_s.strip.downcase
        filtered = q.empty? ? entries : entries.select { |e| e['filename'].to_s.downcase.include?(q) }
        if filtered.empty?
          "🔍 Sin resultados para `#{q}`."
        else
          lines = filtered.last(20).map { |e| "• #{e['filename']} (#{e['size']}B) — #{Time.at(e['timestamp']).strftime('%Y-%m-%d %H:%M')}" }
          "🔍 **Resultados (#{filtered.length}):**\n#{lines.join("\n")}"
        end
      when 'stats'
        total_size = entries.sum { |e| e['size'].to_i }
        "📦 **Vault:** #{entries.length} archivos, #{total_size / 1024} KB indexados."
      else
        if entries.empty?
          "📂 La bóveda está vacía. Sube archivos al canal <##{VAULT_CHANNEL}> para indexarlos."
        else
          lines = entries.last(15).map { |e| "• [#{e['filename']}](#{e['url']}) (#{e['size']}B)" }
          "📂 **Archivos indexados (#{entries.length}):**\n#{lines.join("\n")}"
        end
      end
    rescue StandardError => e
      "Error en vault: #{e.message}"
    end

    def build_backup_response(event, action)
      return '❌ No se pudo obtener el canal de bóveda. Configura DISCORD_VAULT_CHANNEL.' if VAULT_CHANNEL.nil? || VAULT_CHANNEL.empty?

      channel = vault_channel
      return '❌ No se encontró el canal de bóveda.' unless channel

      tmp_dir = File.join(Dir.tmpdir, "aura_backup_#{Time.now.to_i}")
      FileUtils.mkdir_p(tmp_dir)

      begin
        case action
        when 'story'
          data = call_backend('GET', build_backend_path('/api/story/backup'))
          return '❌ Error obteniendo backup de story: ' + (data[:error] || data['error'] || 'desconocido') if data.is_a?(Hash) && (data[:error] || data['error'])
          filename = upload_backup_to_vault(channel, data, "story_backup_#{Time.now.to_i}.json", tmp_dir)
          "📦 **Story backup subido:** #{filename}"
        when 'sessions'
          data = call_backend('GET', build_backend_path('/api/story/backup'))
          return '❌ Error obteniendo sessions: ' + (data[:error] || data['error'] || 'desconocido') if data.is_a?(Hash) && (data[:error] || data['error'])
          sessions = data.is_a?(Hash) ? (data[:sessions] || data['sessions']) : {}
          filename = upload_backup_to_vault(channel, sessions, "sessions_backup_#{Time.now.to_i}.json", tmp_dir)
          "📦 **Sessions backup subido:** #{filename}"
        when 'all'
          data = call_backend('GET', build_backend_path('/api/story/backup'))
          return '❌ Error obteniendo backup completo: ' + (data[:error] || data['error'] || 'desconocido') if data.is_a?(Hash) && (data[:error] || data['error'])
          filename = upload_backup_to_vault(channel, data, "aura_full_backup_#{Time.now.to_i}.json", tmp_dir)
          "📦 **Backup completo subido:** #{filename}"
        else
          'Acción no reconocida. Usa: all, story o sessions.'
        end
      ensure
        FileUtils.rm_rf(tmp_dir) if File.directory?(tmp_dir)
      end
    rescue => e
      "❌ Error en backup: #{e.message}"
    end

    def upload_backup_to_vault(channel, data, filename, tmp_dir)
      path = File.join(tmp_dir, filename)
      File.write(path, JSON.pretty_generate(data))
      channel.send_file(path)
      filename
    end

    def vault_channel
      return unless VAULT_CHANNEL && !VAULT_CHANNEL.empty?
      @bot.channel(VAULT_CHANNEL.to_i) || @bot.channels.find { |c| c.name == VAULT_CHANNEL }
    rescue StandardError
      nil
    end

    def build_command_response(command, options = {})
      case command
      when 'story'
        build_story_response(nil, options['action'] || options[:action] || 'status',
                             options['work'] || options[:work],
                             options['character'] || options[:character],
                             options['text'] || options[:text])
      when 'status'
        service = options['service'] || options[:service]
        response = call_backend('GET', build_backend_path('/api/status'))
        format_status_response(response, service)
      when 'logs'
        service = options['service'] || options[:service] || 'backend'
        lines = options['lines'] || options[:lines] || 50
        response = call_backend('GET', build_backend_path('/api/logs', service: service, lines: lines))
        format_logs_response(response, service, lines)
      when 'restart'
        service = options['service'] || options[:service] || 'backend'
        response = call_backend('POST', build_backend_path('/api/restart'), { service: service })
        format_backend_result(response, "Restart for #{service}")
      when 'deploy'
        service = options['service'] || options[:service] || 'backend'
        response = call_backend('POST', build_backend_path('/api/deploy'), { service: service })
        format_backend_result(response, "Deploy for #{service}")
      when 'esoteric'
        language = options['language'] || options[:language] || 'brainfuck'
        generate_esoteric_challenge(language)
      when 'rules'
        action = options['action'] || options[:action] || 'list'
        rule_name = options['rule_name'] || options[:rule_name]
        format_rules_response(action, rule_name)
      when 'vault'
        action = options['action'] || options[:action] || 'list'
        query = options['query'] || options[:query]
        build_vault_response(action, query)
      else
        'Command not supported.'
      end
    rescue StandardError => e
      "Error: #{e.message}"
    end

    def call_backend(method, path, body = nil)
      headers = { 'Content-Type' => 'application/json' }
      headers['X-API-Key'] = ENV['AURA_API_KEY'] if ENV['AURA_API_KEY'] && !ENV['AURA_API_KEY'].empty?
      headers['Authorization'] = auth_header if auth_header

      response = HTTParty.send(method.downcase, path, headers: headers, body: body&.to_json)

      if response.code == 429
        retry_after = response.headers['retry-after'] || response.headers['Retry-After']
        wait_seconds = retry_after ? retry_after.to_i : 5
        warn "[AURA DiscordBot] Backend rate-limited; waiting #{wait_seconds}s"
        sleep(wait_seconds)
        response = HTTParty.send(method.downcase, path, headers: headers, body: body&.to_json)
      end

      JSON.parse(response.body, symbolize_names: true)
    rescue StandardError => e
      { error: e.message }
    end

    def build_backend_path(endpoint, params = {})
      uri = URI.parse(@backend_url)
      uri.path = endpoint
      uri.query = URI.encode_www_form(params)
      uri.to_s
    rescue URI::InvalidURIError
      endpoint
    end

    def legacy_auth_header
      return ENV['AURA_AUTH_HEADER'] if ENV['AURA_AUTH_HEADER'] && !ENV['AURA_AUTH_HEADER'].empty?
      return "Bearer #{ENV['AURA_BEARER_TOKEN']}" if ENV['AURA_BEARER_TOKEN'] && !ENV['AURA_BEARER_TOKEN'].empty?
      return "Bearer #{ENV['AURA_AUTH_TOKEN']}" if ENV['AURA_AUTH_TOKEN'] && !ENV['AURA_AUTH_TOKEN'].empty?

      nil
    end

    def format_status_response(response, service)
      return response[:error] if response.is_a?(Hash) && response.key?(:error)

      if service
        service_payload = response[service.to_sym] || response[service.to_s]
        service_status = if service_payload.is_a?(Hash)
                           service_payload['status'] || service_payload[:status]
                         else
                           service_payload
                         end
        "Status for #{service}: #{service_status.inspect}"
      else
        response.map { |name, payload| "#{name}: #{payload['status'] || payload[:status]}" }.join("\n")
      end
    end

    def format_logs_response(response, service, lines)
      return response[:error] if response.is_a?(Hash) && response.key?(:error)

      "#{service} logs (#{lines} lines):\n#{response[:logs] || response['logs'] || 'No logs available'}"
    end

    def format_backend_result(response, label)
      return response[:error] if response.is_a?(Hash) && response.key?(:error)

      "#{label}: #{response[:message] || response['message'] || 'ok'}"
    end

    def format_rules_response(action, rule_name)
      compiler = Aura::DSLCompiler.new
      sample_rule = <<~DSL
        rule \"hf_space_down\" do
          on event: :hf_health_check
          if status == 504 && retries > 3
            notify :discord, channel: :ops
            redeploy :hf_space
          end
        end
      DSL

      compiled = compiler.compile(sample_rule)
      if action == 'evaluate'
        result = compiler.evaluate(compiled, { 'status' => 504, 'retries' => 4 })
        "Rule #{compiled['rule']} evaluated to #{result}"
      else
        if rule_name
          "Rule #{rule_name}: #{compiled['rule']}"
        else
          "Available rules:\n- #{compiled['rule']}"
        end
      end
    end

    def generate_esoteric_challenge(language)
      challenges = {
        'brainfuck' => '>++++++++[<++++++++>-]<.>+++++++[<+++++++>-]<+.>++++++++[<--------->-]<-.+.+.+.+.',
        'lolcode' => "HAI 1.2\nCAN HAS STDIO?\nVISIBLE \"HELLO WORLD\"\nKTHXBYE",
        'whitespace' => '(spaces and tabs only — invisible)',
        'malbolge' => '(=&%$#"!}1./2\\)w{+-m\'&SaradqpmoM;:>#/$bL%Tk}L"zHOU4=v|WyR\{-UQ0Z:qD\')n'
      }
      "```#{language}\n#{challenges[language] || challenges['brainfuck']}\n```\n*Translate this to: #{language}*"
    end

    def build_chat_response(prompt)
      return 'No prompt provided.' if prompt.nil? || prompt.strip.empty?

      response = call_backend('POST', build_backend_path('/api/chat'), { prompt: prompt, router: true })
      if response.is_a?(Hash) && response[:error]
        "Error: #{response[:error]}"
      else
        response[:reply] || response['reply'] || response[:text] || response['text'] || '(sin respuesta)'
      end
    rescue StandardError => e
      "Error: #{e.message}"
    end

    def build_feedback_response(value)
      return 'Feedback value required.' if value.nil? || value.strip.empty?

      response = call_backend('POST', build_backend_path('/api/feedback'), { feedback: value })
      if response.is_a?(Hash) && response[:error]
        "Feedback error: #{response[:error]}"
      else
        "Feedback registrado: #{value}"
      end
    rescue StandardError => e
      "Error: #{e.message}"
    end

    def auth_header
      return ENV.fetch('AURA_AUTH_HEADER') unless ENV.fetch('AURA_AUTH_HEADER', '').empty?
      return 'Bearer ' + ENV.fetch('AURA_BEARER_TOKEN') unless ENV.fetch('AURA_BEARER_TOKEN', '').empty?
      return 'Bearer ' + ENV.fetch('AURA_AUTH_TOKEN') unless ENV.fetch('AURA_AUTH_TOKEN', '').empty?

      nil
    end
  end
end

if $PROGRAM_NAME == __FILE__
  bot = Aura::DiscordBot.new
  bot.start
end

package com.ame.ecosystem.api;

import java.util.Map;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;

/**
 * Interfaz Retrofit para el endpoint GBrain Tactical Chat.
 * Se conecta a AURA Core -> Ollama local (sin censura).
 */
public interface GbrainService {

    @POST("/api/v1/gbrain/tactical-chat")
    Call<Map<String, Object>> tacticalChat(@Body TacticalChatRequest request);

    @GET("/api/v1/gbrain/models")
    Call<Map<String, Object>> listModels();

    @GET("/api/v1/gbrain/health")
    Call<Map<String, Object>> healthCheck();

    @POST("/api/v1/gbrain/end-session")
    Call<Map<String, Object>> endSession(@Body EndSessionRequest request);

    // ─── Request Models ───────────────────────────────────────
    class TacticalChatRequest {
        String message;
        String model;
        double temperature;
        String mode;
        String session_id;
        int max_tokens;

        public TacticalChatRequest(String message) {
            this.message = message;
            this.mode = "tactical";
            this.max_tokens = 2048;
            this.temperature = 0.7;
        }

        public TacticalChatRequest(String message, String mode) {
            this(message);
            this.mode = mode;
        }

        public TacticalChatRequest withSession(String sessionId) {
            this.session_id = sessionId;
            return this;
        }

        public TacticalChatRequest withModel(String model) {
            this.model = model;
            return this;
        }

        public TacticalChatRequest withTemperature(double temp) {
            this.temperature = temp;
            return this;
        }
    }

    class EndSessionRequest {
        String session_id;

        public EndSessionRequest(String sessionId) {
            this.session_id = sessionId;
        }
    }
}

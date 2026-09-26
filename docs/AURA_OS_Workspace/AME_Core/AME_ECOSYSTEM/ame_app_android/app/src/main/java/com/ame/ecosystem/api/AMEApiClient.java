package com.ame.ecosystem.api;

import java.util.Map;

import com.google.gson.annotations.SerializedName;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Call;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;

// ─── Data Models ────────────────────────────────────────────
class SherlockRequest {
    @SerializedName("username") String username;
    @SerializedName("timeout") int timeout = 60;
    SherlockRequest(String u) { this.username = u; }
}

class NmapRequest {
    @SerializedName("target") String target;
    @SerializedName("scan_type") String scanType = "quick";
    @SerializedName("timeout") int timeout = 300;
    NmapRequest(String t) { this.target = t; }
}

class OSINTRequest {
    @SerializedName("query") String query;
    @SerializedName("module") String module = "all";
    OSINTRequest(String q) { this.query = q; }
}

class ChatRequest {
    @SerializedName("message") String message;
    @SerializedName("model") String model = "gpt-4o-mini";
    ChatRequest(String m) { this.message = m; }
}

// ─── API Interface ─────────────────────────────────────────
interface AMEService {
    @POST("/api/v1/sherlock")
    Call<Map<String, Object>> sherlock(@Body SherlockRequest req);

    @POST("/api/v1/nmap")
    Call<Map<String, Object>> nmap(@Body NmapRequest req);

    @POST("/api/v1/osint")
    Call<Map<String, Object>> osint(@Body OSINTRequest req);

    @POST("/api/v1/chat")
    Call<Map<String, Object>> chat(@Body ChatRequest req);

    @GET("/api/v1/status")
    Call<Map<String, Object>> status();

    @GET("/api/v1/tools")
    Call<Map<String, Object>> tools();

    @GET("/api/v1/reports")
    Call<Map<String, Object>> reports();
}

// ─── Client Singleton ───────────────────────────────────────
public class AMEApiClient {
    private static AMEApiClient instance;
    private AMEService service;
    // URL para emulador: 10.0.2.2 apunta al host (localhost de la PC)
    // En produccion: cambiar a la IP real del servidor AURA Core
    private String baseUrl = "http://10.0.2.2:8765";

    private AMEApiClient() {
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.setLevel(HttpLoggingInterceptor.Level.BODY);
        OkHttpClient client = new OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(120, java.util.concurrent.TimeUnit.SECONDS)
            .build();

        Retrofit retrofit = new Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build();
        service = retrofit.create(AMEService.class);
    }

    public static synchronized AMEApiClient getInstance() {
        if (instance == null) instance = new AMEApiClient();
        return instance;
    }

    public AMEService getService() { return service; }
    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String url) { this.baseUrl = url; }
}

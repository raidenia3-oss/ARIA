package com.ame.ecosystem.api;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/**
 * Cliente Retrofit para GBrain Tactical Chat.
 * Reutiliza la misma URL base que AMEApiClient (10.0.2.2:8765).
 */
public class GbrainApiClient {
    private static GbrainApiClient instance;
    private GbrainService service;
    private String baseUrl = "http://10.0.2.2:8765";

    private GbrainApiClient() {
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.setLevel(HttpLoggingInterceptor.Level.BASIC);

        OkHttpClient client = new OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(180, java.util.concurrent.TimeUnit.SECONDS) // 3 min para modelos pesados
            .build();

        Retrofit retrofit = new Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build();

        service = retrofit.create(GbrainService.class);
    }

    public static synchronized GbrainApiClient getInstance() {
        if (instance == null) instance = new GbrainApiClient();
        return instance;
    }

    public GbrainService getService() {
        return service;
    }

    public void setBaseUrl(String url) {
        this.baseUrl = url;
        // Resetear instancia para aplicar nueva URL
        instance = null;
    }
}

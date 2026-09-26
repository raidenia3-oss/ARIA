package com.ame.ecosystem.api;

import java.util.Map;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Call;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class OsintApiClient {
    private static OsintApiClient instance;
    private OsintService service;
    private String baseUrl = "http://10.0.2.2:5000";

    private OsintApiClient() {
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.setLevel(HttpLoggingInterceptor.Level.BASIC);
        OkHttpClient client = new OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(300, java.util.concurrent.TimeUnit.SECONDS)
            .build();

        Retrofit retrofit = new Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build();
        service = retrofit.create(OsintService.class);
    }

    public static synchronized OsintApiClient getInstance() {
        if (instance == null) instance = new OsintApiClient();
        return instance;
    }

    public OsintService getService() {
        return service;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String url) {
        this.baseUrl = url;
    }
}
package com.ame.ecosystem.api;

import java.util.Map;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;

public interface OsintService {
    @GET("/api/v1/osint/health")
    Call<Map<String, Object>> health();

    @POST("/api/v1/osint/scan-target")
    Call<Map<String, Object>> scanTarget(@Body OSINTScanRequest request);

    @POST("/api/v1/osint/google-dork")
    Call<Map<String, Object>> generateDork(@Body GoogleDorkRequest request);

    @GET("/api/v1/osint/framework-tree")
    Call<Map<String, Object>> getFrameworkTree();

    @GET("/api/v1/osint/google-dork-templates")
    Call<Map<String, Object>> getDorkTemplates();
}
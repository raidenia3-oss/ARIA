package com.ame.ecosystem.api;

import com.google.gson.annotations.SerializedName;

public class OSINTScanRequest {
    @SerializedName("target")
    public String target;

    @SerializedName("target_type")
    public String targetType = "auto";

    @SerializedName("tools")
    public String[] tools;

    public OSINTScanRequest(String target) {
        this.target = target;
    }

    public OSINTScanRequest(String target, String targetType) {
        this.target = target;
        this.targetType = targetType;
    }
}
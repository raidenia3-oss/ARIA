package com.ame.ecosystem.api;

import com.google.gson.annotations.SerializedName;

public class GoogleDorkRequest {
    @SerializedName("term")
    public String term;

    @SerializedName("file_type")
    public String fileType = "pdf";

    @SerializedName("site")
    public String site;

    public GoogleDorkRequest(String term, String fileType) {
        this.term = term;
        this.fileType = fileType;
    }

    public GoogleDorkRequest(String term, String fileType, String site) {
        this.term = term;
        this.fileType = fileType;
        this.site = site;
    }
}
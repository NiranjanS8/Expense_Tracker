package com.expensetracker.export.entity;

public enum ExpenseExportJobType {
    CSV("text/csv", "csv"),
    PDF("application/pdf", "pdf");

    private final String contentType;
    private final String fileExtension;

    ExpenseExportJobType(String contentType, String fileExtension) {
        this.contentType = contentType;
        this.fileExtension = fileExtension;
    }

    public String contentType() {
        return contentType;
    }

    public String fileExtension() {
        return fileExtension;
    }
}

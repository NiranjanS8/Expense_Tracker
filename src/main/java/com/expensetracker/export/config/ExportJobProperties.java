package com.expensetracker.export.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "app.exports.jobs")
public record ExportJobProperties(
        @NotBlank String storageDir,
        @Min(1) int batchSize
) {
}

package com.expensetracker.email.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.email.reports")
public record EmailReportProperties(
        boolean enabled,
        String cron,
        String from
) {
}

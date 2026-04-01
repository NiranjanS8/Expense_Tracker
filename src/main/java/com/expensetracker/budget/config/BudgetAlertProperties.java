package com.expensetracker.budget.config;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.budget.alert")
public record BudgetAlertProperties(
        List<Integer> thresholds
) {
}

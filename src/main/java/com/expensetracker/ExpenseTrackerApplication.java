package com.expensetracker;

import com.expensetracker.budget.config.BudgetAlertProperties;
import com.expensetracker.email.config.EmailReportProperties;
import com.expensetracker.export.config.ExportJobProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableConfigurationProperties({BudgetAlertProperties.class, EmailReportProperties.class, ExportJobProperties.class})
@EnableScheduling
public class ExpenseTrackerApplication {

    public static void main(String[] args) {
        SpringApplication.run(ExpenseTrackerApplication.class, args);
    }
}

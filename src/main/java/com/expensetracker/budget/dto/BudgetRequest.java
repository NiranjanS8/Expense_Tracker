package com.expensetracker.budget.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;

public record BudgetRequest(
        @NotNull(message = "Amount is required")
        @DecimalMin(value = "0.01", message = "Amount must be greater than zero")
        BigDecimal amount,

        @NotNull(message = "Budget month is required")
        @Pattern(regexp = "^\\d{4}-\\d{2}$", message = "Budget month must be in yyyy-MM format")
        String budgetMonth
) {
}

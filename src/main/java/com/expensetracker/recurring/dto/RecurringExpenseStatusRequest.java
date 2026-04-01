package com.expensetracker.recurring.dto;

import jakarta.validation.constraints.NotNull;

public record RecurringExpenseStatusRequest(
        @NotNull(message = "active is required")
        Boolean active
) {
}

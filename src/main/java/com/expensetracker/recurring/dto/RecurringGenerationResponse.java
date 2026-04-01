package com.expensetracker.recurring.dto;

import java.time.LocalDate;

public record RecurringGenerationResponse(
        LocalDate runDate,
        int recurringRulesProcessed,
        int expensesGenerated
) {
}

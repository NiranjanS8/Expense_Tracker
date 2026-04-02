package com.expensetracker.budget.event;

import java.math.BigDecimal;
import java.time.YearMonth;

public record BudgetChangedEvent(
        Long budgetId,
        Long userId,
        YearMonth budgetMonth,
        BigDecimal amount,
        BudgetChangeType changeType
) {
}

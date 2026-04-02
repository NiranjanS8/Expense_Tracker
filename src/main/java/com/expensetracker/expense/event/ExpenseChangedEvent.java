package com.expensetracker.expense.event;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseChangedEvent(
        Long expenseId,
        Long userId,
        Long categoryId,
        LocalDate expenseDate,
        BigDecimal amount,
        ExpenseChangeType changeType
) {
}

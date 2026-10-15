package com.expensetracker.expense.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseSummaryResponse(
        BigDecimal totalAmount,
        long transactionCount,
        LocalDate startDate,
        LocalDate endDate
) {
}

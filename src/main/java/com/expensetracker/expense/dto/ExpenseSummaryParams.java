package com.expensetracker.expense.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseSummaryParams(
        LocalDate startDate,
        LocalDate endDate,
        Long categoryId,
        BigDecimal minAmount,
        BigDecimal maxAmount,
        String search
) {
}

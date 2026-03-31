package com.expensetracker.expense.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseQueryParams(
        int page,
        int size,
        String sortBy,
        String sortDir,
        String search,
        Long categoryId,
        LocalDate startDate,
        LocalDate endDate,
        BigDecimal minAmount,
        BigDecimal maxAmount
) {
}

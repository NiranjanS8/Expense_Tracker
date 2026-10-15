package com.expensetracker.expense.repository;

import java.math.BigDecimal;

public record ExpenseAggregate(
        BigDecimal totalAmount,
        long transactionCount
) {
}

package com.expensetracker.budget.dto;

import com.expensetracker.budget.entity.Budget;
import java.math.BigDecimal;
import java.time.YearMonth;

public record BudgetResponse(
        Long id,
        BigDecimal amount,
        YearMonth budgetMonth
) {
    public static BudgetResponse from(Budget budget) {
        return new BudgetResponse(
                budget.getId(),
                budget.getAmount(),
                budget.getBudgetMonth()
        );
    }
}

package com.expensetracker.budget.dto;

import com.expensetracker.budget.entity.Budget;
import java.math.BigDecimal;
import java.time.YearMonth;

public record BudgetResponse(
        Long id,
        BigDecimal amount,
        YearMonth budgetMonth,
        BigDecimal spentAmount,
        BigDecimal remainingAmount,
        BigDecimal overBudgetAmount,
        BigDecimal usagePercentage
) {
    public static BudgetResponse from(
            Budget budget,
            BigDecimal spentAmount,
            BigDecimal remainingAmount,
            BigDecimal overBudgetAmount,
            BigDecimal usagePercentage
    ) {
        return new BudgetResponse(
                budget.getId(),
                budget.getAmount(),
                budget.getBudgetMonth(),
                spentAmount,
                remainingAmount,
                overBudgetAmount,
                usagePercentage
        );
    }
}

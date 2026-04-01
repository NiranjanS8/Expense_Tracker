package com.expensetracker.budget.dto;

import com.expensetracker.budget.entity.Budget;
import java.math.BigDecimal;
import java.time.YearMonth;

public record BudgetSummaryResponse(
        Long id,
        BigDecimal budgetAmount,
        YearMonth budgetMonth,
        BigDecimal spentAmount,
        BigDecimal remainingAmount,
        BigDecimal overBudgetAmount,
        BigDecimal usagePercentage,
        boolean exceeded,
        boolean hasRemainingBudget,
        BudgetStatus status
) {
    public static BudgetSummaryResponse from(
            Budget budget,
            BigDecimal spentAmount,
            BigDecimal remainingAmount,
            BigDecimal overBudgetAmount,
            BigDecimal usagePercentage
    ) {
        boolean exceeded = overBudgetAmount.compareTo(BigDecimal.ZERO) > 0;
        boolean hasRemainingBudget = remainingAmount.compareTo(BigDecimal.ZERO) > 0;

        return new BudgetSummaryResponse(
                budget.getId(),
                budget.getAmount(),
                budget.getBudgetMonth(),
                spentAmount,
                remainingAmount,
                overBudgetAmount,
                usagePercentage,
                exceeded,
                hasRemainingBudget,
                exceeded ? BudgetStatus.EXCEEDED : BudgetStatus.ON_TRACK
        );
    }
}

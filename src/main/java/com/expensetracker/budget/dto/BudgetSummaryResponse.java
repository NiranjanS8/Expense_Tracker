package com.expensetracker.budget.dto;

import com.expensetracker.budget.entity.Budget;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.util.List;

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
        BudgetStatus status,
        BudgetAlertLevel alertLevel,
        String alertMessage,
        List<Integer> triggeredThresholds
) {
    public static BudgetSummaryResponse from(
            Budget budget,
            BigDecimal spentAmount,
            BigDecimal remainingAmount,
            BigDecimal overBudgetAmount,
            BigDecimal usagePercentage,
            BudgetStatus status,
            BudgetAlertLevel alertLevel,
            String alertMessage,
            List<Integer> triggeredThresholds
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
                status,
                alertLevel,
                alertMessage,
                triggeredThresholds
        );
    }

    public static BudgetSummaryResponse empty(YearMonth budgetMonth) {
        return new BudgetSummaryResponse(
                null,
                BigDecimal.ZERO,
                budgetMonth,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                false,
                false,
                BudgetStatus.ON_TRACK,
                BudgetAlertLevel.NONE,
                "No budget has been set for this month yet.",
                List.of()
        );
    }
}

package com.expensetracker.budget.dto;

import java.time.YearMonth;

public record BudgetQueryParams(
        YearMonth budgetMonth,
        Integer year
) {
}

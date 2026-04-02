package com.expensetracker.budget.dto;

public record BudgetQueryParams(
        String budgetMonth,
        Integer year
) {
}

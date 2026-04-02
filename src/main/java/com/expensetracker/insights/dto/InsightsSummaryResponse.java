package com.expensetracker.insights.dto;

import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.expense.dto.ExpenseResponse;

import java.math.BigDecimal;
import java.time.YearMonth;
import java.util.List;

public record InsightsSummaryResponse(
        YearMonth month,
        BigDecimal currentMonthTotal,
        BigDecimal previousMonthTotal,
        BigDecimal absoluteChange,
        BigDecimal percentageChange,
        BigDecimal averageDailySpend,
        CategorySpendingResponse topCategory,
        BigDecimal topCategorySharePercentage,
        ExpenseResponse largestExpense,
        List<InsightItemResponse> insights
) {
}

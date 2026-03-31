package com.expensetracker.dashboard.dto;

import com.expensetracker.expense.dto.ExpenseResponse;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.util.List;

public record DashboardSummaryResponse(
        YearMonth month,
        BigDecimal monthlyTotal,
        long transactionCount,
        List<ExpenseResponse> recentTransactions
) {
}

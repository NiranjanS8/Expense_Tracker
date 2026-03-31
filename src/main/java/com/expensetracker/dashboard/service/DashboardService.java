package com.expensetracker.dashboard.service;

import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.dashboard.dto.ChartDataResponse;
import com.expensetracker.dashboard.dto.DashboardSummaryResponse;
import com.expensetracker.dashboard.dto.MonthlyTrendPointResponse;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class DashboardService {

    private final ExpenseRepository expenseRepository;

    @Transactional(readOnly = true)
    public DashboardSummaryResponse getSummary(User user, YearMonth month, int recentLimit) {
        LocalDate startDate = month.atDay(1);
        LocalDate endDate = month.atEndOfMonth();

        BigDecimal monthlyTotal = expenseRepository.sumAmountByUserIdAndExpenseDateBetween(user.getId(), startDate, endDate);
        long transactionCount = expenseRepository.countByUserIdAndExpenseDateBetween(user.getId(), startDate, endDate);
        List<ExpenseResponse> recentTransactions = expenseRepository
                .findTopByUserIdOrderByExpenseDateDescIdDesc(user.getId(), recentLimit)
                .stream()
                .map(ExpenseResponse::from)
                .toList();

        return new DashboardSummaryResponse(
                month,
                defaultAmount(monthlyTotal),
                transactionCount,
                recentTransactions
        );
    }

    @Transactional(readOnly = true)
    public List<CategorySpendingResponse> getCategoryInsights(User user, YearMonth month) {
        return expenseRepository.findCategorySpendingByUserIdAndExpenseDateBetween(
                user.getId(),
                month.atDay(1),
                month.atEndOfMonth()
        );
    }

    @Transactional(readOnly = true)
    public List<MonthlyTrendPointResponse> getMonthlyTrends(User user, int months) {
        LocalDate startDate = YearMonth.now().minusMonths(months - 1L).atDay(1);
        List<Object[]> rows = expenseRepository.findMonthlyTrendByUserIdFromDate(user.getId(), startDate);

        return rows.stream()
                .map(this::mapTrendRow)
                .toList();
    }

    @Transactional(readOnly = true)
    public ChartDataResponse getChartData(User user, YearMonth month, int months) {
        List<CategorySpendingResponse> categorySpending = getCategoryInsights(user, month);
        List<MonthlyTrendPointResponse> monthlyTrends = getMonthlyTrends(user, months);

        return new ChartDataResponse(categorySpending, categorySpending, monthlyTrends);
    }

    private MonthlyTrendPointResponse mapTrendRow(Object[] row) {
        int year = ((Number) row[0]).intValue();
        int month = ((Number) row[1]).intValue();
        BigDecimal total = row[2] == null ? BigDecimal.ZERO : (BigDecimal) row[2];

        return new MonthlyTrendPointResponse(YearMonth.of(year, month), total);
    }

    private BigDecimal defaultAmount(BigDecimal amount) {
        return amount == null ? BigDecimal.ZERO : amount;
    }
}

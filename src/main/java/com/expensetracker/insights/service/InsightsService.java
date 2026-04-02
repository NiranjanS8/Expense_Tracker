package com.expensetracker.insights.service;

import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.insights.dto.InsightItemResponse;
import com.expensetracker.insights.dto.InsightsSummaryResponse;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class InsightsService {

    private final ExpenseRepository expenseRepository;

    @Transactional(readOnly = true)
    public InsightsSummaryResponse getInsightsSummary(User user, YearMonth month) {
        YearMonth previousMonth = month.minusMonths(1);
        LocalDate currentStart = month.atDay(1);
        LocalDate currentEnd = month.atEndOfMonth();
        LocalDate previousStart = previousMonth.atDay(1);
        LocalDate previousEnd = previousMonth.atEndOfMonth();

        BigDecimal currentMonthTotal = defaultAmount(expenseRepository
                .sumAmountByUserIdAndExpenseDateBetween(user.getId(), currentStart, currentEnd));
        BigDecimal previousMonthTotal = defaultAmount(expenseRepository
                .sumAmountByUserIdAndExpenseDateBetween(user.getId(), previousStart, previousEnd));
        BigDecimal absoluteChange = currentMonthTotal.subtract(previousMonthTotal);
        BigDecimal percentageChange = calculateChangePercentage(currentMonthTotal, previousMonthTotal);
        BigDecimal averageDailySpend = calculateAverageDailySpend(currentMonthTotal, month.lengthOfMonth());

        List<CategorySpendingResponse> categorySpend = expenseRepository.findCategorySpendingByUserIdAndExpenseDateBetween(
                user.getId(),
                currentStart,
                currentEnd
        );
        CategorySpendingResponse topCategory = categorySpend.isEmpty() ? null : categorySpend.getFirst();
        BigDecimal topCategorySharePercentage = topCategory == null
                ? BigDecimal.ZERO
                : percentageOf(topCategory.totalAmount(), currentMonthTotal);

        ExpenseResponse largestExpense = expenseRepository.findTopByUserIdAndExpenseDateBetweenOrderByAmountDescIdDesc(
                        user.getId(),
                        currentStart,
                        currentEnd,
                        Pageable.ofSize(1)
                )
                .stream()
                .findFirst()
                .map(ExpenseResponse::from)
                .orElse(null);

        List<InsightItemResponse> insights = buildInsights(
                month,
                currentMonthTotal,
                previousMonthTotal,
                absoluteChange,
                percentageChange,
                averageDailySpend,
                topCategory,
                topCategorySharePercentage,
                largestExpense
        );

        return new InsightsSummaryResponse(
                month,
                currentMonthTotal,
                previousMonthTotal,
                absoluteChange,
                percentageChange,
                averageDailySpend,
                topCategory,
                topCategorySharePercentage,
                largestExpense,
                insights
        );
    }

    private List<InsightItemResponse> buildInsights(
            YearMonth month,
            BigDecimal currentMonthTotal,
            BigDecimal previousMonthTotal,
            BigDecimal absoluteChange,
            BigDecimal percentageChange,
            BigDecimal averageDailySpend,
            CategorySpendingResponse topCategory,
            BigDecimal topCategorySharePercentage,
            ExpenseResponse largestExpense
    ) {
        List<InsightItemResponse> insights = new ArrayList<>();

        if (currentMonthTotal.compareTo(BigDecimal.ZERO) == 0) {
            insights.add(new InsightItemResponse(
                    "summary",
                    "No spending recorded",
                    "No expenses were recorded for " + month + "."
            ));
            return insights;
        }

        if (previousMonthTotal.compareTo(BigDecimal.ZERO) == 0) {
            insights.add(new InsightItemResponse(
                    "comparison",
                    "Fresh baseline",
                    "This is your first spending month with usable data for comparison."
            ));
        } else if (absoluteChange.compareTo(BigDecimal.ZERO) > 0) {
            insights.add(new InsightItemResponse(
                    "comparison",
                    "Spending increased",
                    "Spending is up by " + absoluteChange + " (" + percentageChange + "%) compared with last month."
            ));
        } else if (absoluteChange.compareTo(BigDecimal.ZERO) < 0) {
            insights.add(new InsightItemResponse(
                    "comparison",
                    "Spending decreased",
                    "Spending is down by " + absoluteChange.abs() + " (" + percentageChange.abs()
                            + "%) compared with last month."
            ));
        } else {
            insights.add(new InsightItemResponse(
                    "comparison",
                    "Spending unchanged",
                    "Spending matched last month exactly."
            ));
        }

        if (topCategory != null) {
            insights.add(new InsightItemResponse(
                    "category",
                    "Top spending category",
                    topCategory.categoryName() + " accounts for " + topCategorySharePercentage
                            + "% of this month's spending."
            ));
        }

        if (largestExpense != null) {
            insights.add(new InsightItemResponse(
                    "transaction",
                    "Largest expense",
                    "The biggest expense this month was " + largestExpense.amount() + " for "
                            + largestExpense.categoryName() + " on " + largestExpense.expenseDate() + "."
            ));
        }

        insights.add(new InsightItemResponse(
                "habit",
                "Average daily spend",
                "Average daily spend for " + month + " is " + averageDailySpend + "."
        ));

        return insights;
    }

    private BigDecimal calculateChangePercentage(BigDecimal current, BigDecimal previous) {
        if (previous.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }

        return current.subtract(previous)
                .multiply(BigDecimal.valueOf(100))
                .divide(previous, 2, RoundingMode.HALF_UP);
    }

    private BigDecimal calculateAverageDailySpend(BigDecimal total, int daysInMonth) {
        if (daysInMonth <= 0) {
            return BigDecimal.ZERO;
        }

        return total.divide(BigDecimal.valueOf(daysInMonth), 2, RoundingMode.HALF_UP);
    }

    private BigDecimal percentageOf(BigDecimal part, BigDecimal total) {
        if (total == null || total.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }

        return part.multiply(BigDecimal.valueOf(100))
                .divide(total, 2, RoundingMode.HALF_UP);
    }

    private BigDecimal defaultAmount(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }
}

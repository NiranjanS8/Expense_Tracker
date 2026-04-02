package com.expensetracker.budget.service;

import com.expensetracker.budget.config.BudgetAlertProperties;
import com.expensetracker.budget.dto.BudgetAlertLevel;
import com.expensetracker.budget.dto.BudgetQueryParams;
import com.expensetracker.budget.dto.BudgetStatus;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.YearMonth;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class BudgetQueryService {

    private final BudgetRepository budgetRepository;
    private final ExpenseRepository expenseRepository;
    private final BudgetAlertProperties budgetAlertProperties;

    @Transactional(readOnly = true)
    public BudgetSummaryResponse getBudgetByMonth(String budgetMonthValue, User user) {
        YearMonth budgetMonth = parseBudgetMonth(budgetMonthValue);
        validateBudgetMonth(budgetMonth);
        return toBudgetResponse(findBudgetByMonth(user.getId(), budgetMonth));
    }

    @Transactional(readOnly = true)
    public BudgetSummaryResponse getCurrentMonthBudget(User user) {
        YearMonth currentMonth = YearMonth.now();
        return budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())
                .stream()
                .filter(budget -> budget.getBudgetMonth().equals(currentMonth))
                .findFirst()
                .map(this::toBudgetResponse)
                .orElseGet(() -> BudgetSummaryResponse.empty(currentMonth));
    }

    @Transactional(readOnly = true)
    public List<BudgetSummaryResponse> getBudgetHistory(BudgetQueryParams queryParams, User user) {
        if (queryParams.year() != null && queryParams.budgetMonth() != null) {
            throw new BadRequestException("Use either year or budgetMonth in history queries, not both");
        }

        List<Budget> budgets;
        if (queryParams.budgetMonth() != null) {
            YearMonth budgetMonth = parseBudgetMonth(queryParams.budgetMonth());
            validateBudgetMonth(budgetMonth);
            budgets = budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())
                    .stream()
                    .filter(budget -> budget.getBudgetMonth().equals(budgetMonth))
                    .toList();
        } else if (queryParams.year() != null) {
            budgets = budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())
                    .stream()
                    .filter(budget -> budget.getBudgetMonth().getYear() == queryParams.year())
                    .toList();
        } else {
            budgets = budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId());
        }

        return budgets.stream()
                .map(this::toBudgetResponse)
                .toList();
    }

    @Transactional(readOnly = true)
    public Budget findBudgetByMonth(Long userId, YearMonth budgetMonth) {
        return budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(userId)
                .stream()
                .filter(budget -> budget.getBudgetMonth().equals(budgetMonth))
                .findFirst()
                .orElseThrow(() -> new ResourceNotFoundException("Budget not found for the given month"));
    }

    @Transactional(readOnly = true)
    public boolean hasBudgetForMonth(Long userId, YearMonth budgetMonth) {
        return budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(userId)
                .stream()
                .anyMatch(budget -> budget.getBudgetMonth().equals(budgetMonth));
    }

    @Transactional(readOnly = true)
    public BudgetSummaryResponse toBudgetResponse(Budget budget) {
        BigDecimal spentAmount = expenseRepository.sumAmountByUserIdAndExpenseDateBetween(
                budget.getUser().getId(),
                budget.getBudgetMonth().atDay(1),
                budget.getBudgetMonth().atEndOfMonth()
        );
        BigDecimal safeSpentAmount = defaultAmount(spentAmount);
        BigDecimal budgetAmount = budget.getAmount();
        BigDecimal remainingAmount = budgetAmount.subtract(safeSpentAmount).max(BigDecimal.ZERO);
        BigDecimal overBudgetAmount = safeSpentAmount.subtract(budgetAmount).max(BigDecimal.ZERO);
        BigDecimal usagePercentage = calculateUsagePercentage(safeSpentAmount, budgetAmount);
        List<Integer> triggeredThresholds = resolveTriggeredThresholds(usagePercentage);
        BudgetStatus status = resolveStatus(overBudgetAmount, triggeredThresholds);
        BudgetAlertLevel alertLevel = resolveAlertLevel(status);
        String alertMessage = buildAlertMessage(status, usagePercentage, triggeredThresholds);

        return BudgetSummaryResponse.from(
                budget,
                safeSpentAmount,
                remainingAmount,
                overBudgetAmount,
                usagePercentage,
                status,
                alertLevel,
                alertMessage,
                triggeredThresholds
        );
    }

    public YearMonth parseBudgetMonth(String budgetMonth) {
        try {
            return YearMonth.parse(budgetMonth);
        } catch (RuntimeException exception) {
            throw new BadRequestException("Budget month must be in yyyy-MM format");
        }
    }

    public void validateBudgetMonth(YearMonth budgetMonth) {
        YearMonth earliestSupportedMonth = YearMonth.of(2000, 1);
        YearMonth latestSupportedMonth = YearMonth.of(2100, 12);

        if (budgetMonth.isBefore(earliestSupportedMonth) || budgetMonth.isAfter(latestSupportedMonth)) {
            throw new BadRequestException("budgetMonth must be between 2000-01 and 2100-12");
        }
    }

    private BigDecimal calculateUsagePercentage(BigDecimal spentAmount, BigDecimal budgetAmount) {
        if (budgetAmount == null || budgetAmount.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }

        return spentAmount
                .multiply(BigDecimal.valueOf(100))
                .divide(budgetAmount, 2, RoundingMode.HALF_UP);
    }

    private BigDecimal defaultAmount(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    private List<Integer> resolveTriggeredThresholds(BigDecimal usagePercentage) {
        List<Integer> thresholds = budgetAlertProperties.thresholds();
        if (thresholds == null || thresholds.isEmpty()) {
            return List.of();
        }

        return thresholds.stream()
                .filter(Objects::nonNull)
                .filter(threshold -> threshold > 0)
                .filter(threshold -> usagePercentage.compareTo(BigDecimal.valueOf(threshold)) >= 0)
                .sorted(Comparator.naturalOrder())
                .toList();
    }

    private BudgetStatus resolveStatus(BigDecimal overBudgetAmount, List<Integer> triggeredThresholds) {
        if (overBudgetAmount.compareTo(BigDecimal.ZERO) > 0) {
            return BudgetStatus.EXCEEDED;
        }
        if (hasTriggeredThreshold(triggeredThresholds, 90)) {
            return BudgetStatus.CRITICAL;
        }
        if (hasTriggeredThreshold(triggeredThresholds, 80)) {
            return BudgetStatus.WARNING;
        }
        return BudgetStatus.ON_TRACK;
    }

    private BudgetAlertLevel resolveAlertLevel(BudgetStatus status) {
        return switch (status) {
            case ON_TRACK -> BudgetAlertLevel.NONE;
            case WARNING -> BudgetAlertLevel.WARNING;
            case CRITICAL -> BudgetAlertLevel.CRITICAL;
            case EXCEEDED -> BudgetAlertLevel.EXCEEDED;
        };
    }

    private String buildAlertMessage(
            BudgetStatus status,
            BigDecimal usagePercentage,
            List<Integer> triggeredThresholds
    ) {
        return switch (status) {
            case ON_TRACK -> "Budget is within the safe spending range.";
            case WARNING -> "Budget usage has crossed " + maxTriggeredThreshold(triggeredThresholds)
                    + "% of the monthly limit.";
            case CRITICAL -> "Budget usage is critically high at " + usagePercentage
                    + "% of the monthly limit.";
            case EXCEEDED -> "Budget has been exceeded for the month.";
        };
    }

    private int maxTriggeredThreshold(List<Integer> triggeredThresholds) {
        return triggeredThresholds.stream()
                .max(Integer::compareTo)
                .orElse(0);
    }

    private boolean hasTriggeredThreshold(List<Integer> triggeredThresholds, int minimumThreshold) {
        return triggeredThresholds.stream().anyMatch(threshold -> threshold >= minimumThreshold);
    }
}

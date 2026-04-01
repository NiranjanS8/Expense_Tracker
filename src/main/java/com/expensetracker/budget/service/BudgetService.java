package com.expensetracker.budget.service;

import com.expensetracker.budget.config.BudgetAlertProperties;
import com.expensetracker.budget.dto.BudgetAlertLevel;
import com.expensetracker.budget.dto.BudgetRequest;
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
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class BudgetService {

    private final BudgetRepository budgetRepository;
    private final ExpenseRepository expenseRepository;
    private final BudgetAlertProperties budgetAlertProperties;

    @Transactional
    public BudgetSummaryResponse createBudget(BudgetRequest request, User user) {
        if (budgetRepository.existsByUserIdAndBudgetMonth(user.getId(), request.budgetMonth())) {
            throw new BadRequestException("Budget already exists for the given month");
        }

        Budget budget = new Budget();
        budget.setUser(user);
        budget.setAmount(request.amount());
        budget.setBudgetMonth(request.budgetMonth());

        return toBudgetResponse(budgetRepository.save(budget));
    }

    @Transactional
    public BudgetSummaryResponse updateBudget(YearMonth budgetMonth, BudgetRequest request, User user) {
        if (!budgetMonth.equals(request.budgetMonth())) {
            throw new BadRequestException("Path month and request budgetMonth must match");
        }

        Budget budget = findBudgetByMonth(user.getId(), budgetMonth);
        budget.setAmount(request.amount());

        return toBudgetResponse(budget);
    }

    @Transactional(readOnly = true)
    public BudgetSummaryResponse getBudgetByMonth(YearMonth budgetMonth, User user) {
        return toBudgetResponse(findBudgetByMonth(user.getId(), budgetMonth));
    }

    @Transactional(readOnly = true)
    public BudgetSummaryResponse getCurrentMonthBudget(User user) {
        return toBudgetResponse(findBudgetByMonth(user.getId(), YearMonth.now()));
    }

    private Budget findBudgetByMonth(Long userId, YearMonth budgetMonth) {
        return budgetRepository.findByUserIdAndBudgetMonth(userId, budgetMonth)
                .orElseThrow(() -> new ResourceNotFoundException("Budget not found for the given month"));
    }

    private BudgetSummaryResponse toBudgetResponse(Budget budget) {
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
        String alertMessage = buildAlertMessage(status, budgetAmount, usagePercentage, triggeredThresholds);

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
        return budgetAlertProperties.thresholds()
                .stream()
                .filter(threshold -> usagePercentage.compareTo(BigDecimal.valueOf(threshold)) >= 0)
                .sorted(Comparator.naturalOrder())
                .toList();
    }

    private BudgetStatus resolveStatus(BigDecimal overBudgetAmount, List<Integer> triggeredThresholds) {
        if (overBudgetAmount.compareTo(BigDecimal.ZERO) > 0) {
            return BudgetStatus.EXCEEDED;
        }
        if (triggeredThresholds.contains(90)) {
            return BudgetStatus.CRITICAL;
        }
        if (triggeredThresholds.contains(80)) {
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
            BigDecimal budgetAmount,
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
}

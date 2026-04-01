package com.expensetracker.budget.service;

import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.YearMonth;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class BudgetService {

    private final BudgetRepository budgetRepository;
    private final ExpenseRepository expenseRepository;

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

        return BudgetSummaryResponse.from(
                budget,
                safeSpentAmount,
                remainingAmount,
                overBudgetAmount,
                usagePercentage
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
}

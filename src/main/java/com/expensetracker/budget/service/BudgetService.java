package com.expensetracker.budget.service;

import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetResponse;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.user.entity.User;
import java.time.YearMonth;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class BudgetService {

    private final BudgetRepository budgetRepository;

    @Transactional
    public BudgetResponse createBudget(BudgetRequest request, User user) {
        if (budgetRepository.existsByUserIdAndBudgetMonth(user.getId(), request.budgetMonth())) {
            throw new BadRequestException("Budget already exists for the given month");
        }

        Budget budget = new Budget();
        budget.setUser(user);
        budget.setAmount(request.amount());
        budget.setBudgetMonth(request.budgetMonth());

        return BudgetResponse.from(budgetRepository.save(budget));
    }

    @Transactional
    public BudgetResponse updateBudget(YearMonth budgetMonth, BudgetRequest request, User user) {
        if (!budgetMonth.equals(request.budgetMonth())) {
            throw new BadRequestException("Path month and request budgetMonth must match");
        }

        Budget budget = findBudgetByMonth(user.getId(), budgetMonth);
        budget.setAmount(request.amount());

        return BudgetResponse.from(budget);
    }

    @Transactional(readOnly = true)
    public BudgetResponse getBudgetByMonth(YearMonth budgetMonth, User user) {
        return BudgetResponse.from(findBudgetByMonth(user.getId(), budgetMonth));
    }

    @Transactional(readOnly = true)
    public BudgetResponse getCurrentMonthBudget(User user) {
        return BudgetResponse.from(findBudgetByMonth(user.getId(), YearMonth.now()));
    }

    private Budget findBudgetByMonth(Long userId, YearMonth budgetMonth) {
        return budgetRepository.findByUserIdAndBudgetMonth(userId, budgetMonth)
                .orElseThrow(() -> new ResourceNotFoundException("Budget not found for the given month"));
    }
}

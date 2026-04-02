package com.expensetracker.budget.service;

import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.event.BudgetChangeType;
import com.expensetracker.budget.event.BudgetChangedEvent;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.user.entity.User;
import java.time.YearMonth;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class BudgetCommandService {

    private final BudgetRepository budgetRepository;
    private final BudgetQueryService budgetQueryService;
    private final ApplicationEventPublisher applicationEventPublisher;

    @Transactional
    public BudgetSummaryResponse createBudget(BudgetRequest request, User user) {
        YearMonth budgetMonth = budgetQueryService.parseBudgetMonth(request.budgetMonth());
        budgetQueryService.validateBudgetMonth(budgetMonth);
        if (budgetQueryService.hasBudgetForMonth(user.getId(), budgetMonth)) {
            throw new BadRequestException("Budget already exists for the given month");
        }

        Budget budget = new Budget();
        budget.setUser(user);
        budget.setAmount(request.amount());
        budget.setBudgetMonth(budgetMonth);

        Budget savedBudget = budgetRepository.save(budget);
        publishBudgetChanged(savedBudget, BudgetChangeType.CREATED);
        return budgetQueryService.toBudgetResponse(savedBudget);
    }

    @Transactional
    public BudgetSummaryResponse updateBudget(String budgetMonthValue, BudgetRequest request, User user) {
        YearMonth budgetMonth = budgetQueryService.parseBudgetMonth(budgetMonthValue);
        YearMonth requestBudgetMonth = budgetQueryService.parseBudgetMonth(request.budgetMonth());
        budgetQueryService.validateBudgetMonth(budgetMonth);
        budgetQueryService.validateBudgetMonth(requestBudgetMonth);
        if (!budgetMonth.equals(requestBudgetMonth)) {
            throw new BadRequestException("Path month and request budgetMonth must match");
        }

        Budget budget = budgetQueryService.findBudgetByMonth(user.getId(), budgetMonth);
        budget.setAmount(request.amount());

        publishBudgetChanged(budget, BudgetChangeType.UPDATED);
        return budgetQueryService.toBudgetResponse(budget);
    }

    private void publishBudgetChanged(Budget budget, BudgetChangeType changeType) {
        applicationEventPublisher.publishEvent(new BudgetChangedEvent(
                budget.getId(),
                budget.getUser().getId(),
                budget.getBudgetMonth(),
                budget.getAmount(),
                changeType
        ));
    }
}

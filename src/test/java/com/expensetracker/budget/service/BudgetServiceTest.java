package com.expensetracker.budget.service;

import com.expensetracker.budget.config.BudgetAlertProperties;
import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetStatus;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertIterableEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BudgetServiceTest {

    @Mock
    private BudgetRepository budgetRepository;

    @Mock
    private ExpenseRepository expenseRepository;

    @Mock
    private BudgetAlertProperties budgetAlertProperties;

    @InjectMocks
    private BudgetService budgetService;

    @Test
    void createBudgetShouldReturnCalculatedCriticalSummary() {
        User user = createUser(1L);
        BudgetRequest request = new BudgetRequest(new BigDecimal("1000.00"), "2026-04");
        Budget savedBudget = createBudget(user, 10L, new BigDecimal("1000.00"), YearMonth.of(2026, 4));

        when(budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())).thenReturn(List.of());
        when(budgetRepository.save(any(Budget.class))).thenReturn(savedBudget);
        when(expenseRepository.sumAmountByUserIdAndExpenseDateBetween(
                eq(user.getId()),
                eq(LocalDate.of(2026, 4, 1)),
                eq(LocalDate.of(2026, 4, 30))
        )).thenReturn(new BigDecimal("900.00"));
        when(budgetAlertProperties.thresholds()).thenReturn(List.of(80, 90, 100));

        BudgetSummaryResponse response = budgetService.createBudget(request, user);

        assertEquals(new BigDecimal("1000.00"), response.budgetAmount());
        assertEquals("2026-04", response.budgetMonth());
        assertEquals(new BigDecimal("900.00"), response.spentAmount());
        assertEquals(new BigDecimal("100.00"), response.remainingAmount());
        assertEquals(new BigDecimal("90.00"), response.usagePercentage());
        assertEquals(BudgetStatus.CRITICAL, response.status());
        assertIterableEquals(List.of(80, 90), response.triggeredThresholds());
        verify(budgetRepository).save(any(Budget.class));
    }

    @Test
    void createBudgetShouldRejectDuplicateMonth() {
        User user = createUser(1L);
        Budget existingBudget = createBudget(user, 20L, new BigDecimal("500.00"), YearMonth.of(2026, 4));

        when(budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())).thenReturn(List.of(existingBudget));

        BadRequestException exception = assertThrows(
                BadRequestException.class,
                () -> budgetService.createBudget(new BudgetRequest(new BigDecimal("1000.00"), "2026-04"), user)
        );

        assertEquals("Budget already exists for the given month", exception.getMessage());
    }

    @Test
    void getCurrentMonthBudgetShouldReturnEmptySummaryWhenNoBudgetExists() {
        User user = createUser(2L);
        YearMonth currentMonth = YearMonth.now();

        when(budgetRepository.findAllByUserIdOrderByBudgetMonthDesc(user.getId())).thenReturn(List.of());

        BudgetSummaryResponse response = budgetService.getCurrentMonthBudget(user);

        assertEquals(currentMonth.toString(), response.budgetMonth());
        assertEquals(BigDecimal.ZERO, response.budgetAmount());
        assertEquals(BudgetStatus.ON_TRACK, response.status());
        assertEquals("No budget has been set for this month yet.", response.alertMessage());
    }

    private User createUser(Long id) {
        User user = new User();
        user.setId(id);
        user.setFullName("Budget Tester");
        user.setEmail("budget@test.com");
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private Budget createBudget(User user, Long id, BigDecimal amount, YearMonth budgetMonth) {
        Budget budget = new Budget();
        budget.setId(id);
        budget.setUser(user);
        budget.setAmount(amount);
        budget.setBudgetMonth(budgetMonth);
        return budget;
    }
}

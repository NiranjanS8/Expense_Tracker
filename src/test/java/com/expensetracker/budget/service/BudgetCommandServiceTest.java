package com.expensetracker.budget.service;

import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.entity.Budget;
import com.expensetracker.budget.event.BudgetChangeType;
import com.expensetracker.budget.event.BudgetChangedEvent;
import com.expensetracker.budget.repository.BudgetRepository;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class BudgetCommandServiceTest {

    @Mock
    private BudgetRepository budgetRepository;

    @Mock
    private BudgetQueryService budgetQueryService;

    @Mock
    private ApplicationEventPublisher applicationEventPublisher;

    private BudgetCommandService budgetCommandService;

    @BeforeEach
    void setUp() {
        budgetCommandService = new BudgetCommandService(
                budgetRepository,
                budgetQueryService,
                applicationEventPublisher
        );
    }

    @Test
    void createBudgetShouldPublishCreatedEvent() {
        User user = createUser(1L);
        BudgetRequest request = new BudgetRequest(new BigDecimal("5000.00"), "2026-04");
        YearMonth budgetMonth = YearMonth.of(2026, 4);
        Budget savedBudget = createBudget(10L, user, budgetMonth, new BigDecimal("5000.00"));

        when(budgetQueryService.parseBudgetMonth("2026-04")).thenReturn(budgetMonth);
        when(budgetRepository.save(any(Budget.class))).thenReturn(savedBudget);
        when(budgetQueryService.toBudgetResponse(savedBudget)).thenReturn(null);

        budgetCommandService.createBudget(request, user);

        ArgumentCaptor<BudgetChangedEvent> eventCaptor = ArgumentCaptor.forClass(BudgetChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        BudgetChangedEvent event = eventCaptor.getValue();
        assertEquals(savedBudget.getId(), event.budgetId());
        assertEquals(user.getId(), event.userId());
        assertEquals(budgetMonth, event.budgetMonth());
        assertEquals(new BigDecimal("5000.00"), event.amount());
        assertEquals(BudgetChangeType.CREATED, event.changeType());
    }

    @Test
    void updateBudgetShouldPublishUpdatedEvent() {
        User user = createUser(2L);
        BudgetRequest request = new BudgetRequest(new BigDecimal("7500.00"), "2026-05");
        YearMonth budgetMonth = YearMonth.of(2026, 5);
        Budget budget = createBudget(11L, user, budgetMonth, new BigDecimal("6000.00"));

        when(budgetQueryService.parseBudgetMonth("2026-05")).thenReturn(budgetMonth);
        when(budgetQueryService.findBudgetByMonth(user.getId(), budgetMonth)).thenReturn(budget);
        when(budgetQueryService.toBudgetResponse(budget)).thenReturn(null);

        budgetCommandService.updateBudget("2026-05", request, user);

        ArgumentCaptor<BudgetChangedEvent> eventCaptor = ArgumentCaptor.forClass(BudgetChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        BudgetChangedEvent event = eventCaptor.getValue();
        assertEquals(BudgetChangeType.UPDATED, event.changeType());
        assertEquals(new BigDecimal("7500.00"), event.amount());
    }

    private User createUser(Long id) {
        User user = new User();
        user.setId(id);
        user.setFullName("Budget Event Tester");
        user.setEmail("budget-event@test.com");
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private Budget createBudget(Long id, User user, YearMonth budgetMonth, BigDecimal amount) {
        Budget budget = new Budget();
        budget.setId(id);
        budget.setUser(user);
        budget.setBudgetMonth(budgetMonth);
        budget.setAmount(amount);
        return budget;
    }
}

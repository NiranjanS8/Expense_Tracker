package com.expensetracker.expense.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.entity.PaymentMethod;
import com.expensetracker.expense.event.ExpenseChangeType;
import com.expensetracker.expense.event.ExpenseChangedEvent;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.smartcategory.service.SmartCategoryService;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ExpenseCommandServiceTest {

    @Mock
    private ExpenseRepository expenseRepository;

    @Mock
    private CategoryService categoryService;

    @Mock
    private SmartCategoryService smartCategoryService;

    @Mock
    private ExpenseQueryService expenseQueryService;

    @Mock
    private ApplicationEventPublisher applicationEventPublisher;

    private ExpenseCommandService expenseCommandService;

    @BeforeEach
    void setUp() {
        expenseCommandService = new ExpenseCommandService(
                expenseRepository,
                categoryService,
                smartCategoryService,
                expenseQueryService,
                applicationEventPublisher
        );
    }

    @Test
    void createExpenseShouldPublishCreatedEvent() {
        User user = createUser(1L);
        Category category = createCategory(10L, "Food");
        ExpenseRequest request = new ExpenseRequest(
                category.getId(),
                new BigDecimal("250.00"),
                LocalDate.of(2026, 4, 2),
                "Lunch",
                PaymentMethod.UPI
        );

        when(categoryService.getAccessibleCategory(category.getId(), user.getId())).thenReturn(category);
        when(expenseRepository.save(any(Expense.class))).thenAnswer(invocation -> {
            Expense savedExpense = invocation.getArgument(0);
            savedExpense.setId(100L);
            return savedExpense;
        });

        expenseCommandService.createExpense(request, user);

        ArgumentCaptor<ExpenseChangedEvent> eventCaptor = ArgumentCaptor.forClass(ExpenseChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        ExpenseChangedEvent event = eventCaptor.getValue();
        assertEquals(100L, event.expenseId());
        assertEquals(user.getId(), event.userId());
        assertEquals(category.getId(), event.categoryId());
        assertEquals(LocalDate.of(2026, 4, 2), event.expenseDate());
        assertEquals(new BigDecimal("250.00"), event.amount());
        assertEquals(ExpenseChangeType.CREATED, event.changeType());
    }

    @Test
    void updateExpenseShouldPublishUpdatedEvent() {
        User user = createUser(1L);
        Category category = createCategory(11L, "Travel");
        Expense expense = createExpense(200L, user, category, new BigDecimal("400.00"), LocalDate.of(2026, 4, 3));
        ExpenseRequest request = new ExpenseRequest(
                category.getId(),
                new BigDecimal("450.00"),
                LocalDate.of(2026, 4, 4),
                "Updated cab fare",
                PaymentMethod.CARD
        );

        when(expenseQueryService.findUserExpense(expense.getId(), user.getId())).thenReturn(expense);
        when(categoryService.getAccessibleCategory(category.getId(), user.getId())).thenReturn(category);

        expenseCommandService.updateExpense(expense.getId(), request, user);

        ArgumentCaptor<ExpenseChangedEvent> eventCaptor = ArgumentCaptor.forClass(ExpenseChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        ExpenseChangedEvent event = eventCaptor.getValue();
        assertEquals(expense.getId(), event.expenseId());
        assertEquals(ExpenseChangeType.UPDATED, event.changeType());
        assertEquals(LocalDate.of(2026, 4, 4), event.expenseDate());
        assertEquals(new BigDecimal("450.00"), event.amount());
    }

    @Test
    void deleteExpenseShouldPublishDeletedEvent() {
        User user = createUser(1L);
        Category category = createCategory(12L, "Bills");
        Expense expense = createExpense(300L, user, category, new BigDecimal("999.00"), LocalDate.of(2026, 4, 5));

        when(expenseQueryService.findUserExpense(expense.getId(), user.getId())).thenReturn(expense);

        expenseCommandService.deleteExpense(expense.getId(), user);

        ArgumentCaptor<ExpenseChangedEvent> eventCaptor = ArgumentCaptor.forClass(ExpenseChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        verify(expenseRepository).delete(eq(expense));
        assertEquals(ExpenseChangeType.DELETED, eventCaptor.getValue().changeType());
    }

    private User createUser(Long id) {
        User user = new User();
        user.setId(id);
        user.setFullName("Expense Tester");
        user.setEmail("expense@test.com");
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private Category createCategory(Long id, String name) {
        Category category = new Category();
        category.setId(id);
        category.setName(name);
        return category;
    }

    private Expense createExpense(Long id, User user, Category category, BigDecimal amount, LocalDate expenseDate) {
        Expense expense = new Expense();
        expense.setId(id);
        expense.setUser(user);
        expense.setCategory(category);
        expense.setAmount(amount);
        expense.setExpenseDate(expenseDate);
        expense.setPaymentMethod(PaymentMethod.CARD);
        return expense;
    }
}

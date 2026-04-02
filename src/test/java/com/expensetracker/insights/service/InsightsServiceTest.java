package com.expensetracker.insights.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.entity.PaymentMethod;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.insights.dto.InsightsSummaryResponse;
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
import org.springframework.data.domain.Pageable;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class InsightsServiceTest {

    @Mock
    private ExpenseRepository expenseRepository;

    @InjectMocks
    private InsightsService insightsService;

    @Test
    void getInsightsSummaryShouldReturnNoSpendingBaselineForEmptyMonth() {
        User user = createUser(1L);
        YearMonth month = YearMonth.of(2026, 4);

        when(expenseRepository.sumAmountByUserIdAndExpenseDateBetween(eq(user.getId()), any(LocalDate.class), any(LocalDate.class)))
                .thenReturn(BigDecimal.ZERO);
        when(expenseRepository.findCategorySpendingByUserIdAndExpenseDateBetween(eq(user.getId()), any(LocalDate.class), any(LocalDate.class)))
                .thenReturn(List.of());
        when(expenseRepository.findTopByUserIdAndExpenseDateBetweenOrderByAmountDescIdDesc(
                eq(user.getId()),
                any(LocalDate.class),
                any(LocalDate.class),
                any(Pageable.class)
        )).thenReturn(List.of());

        InsightsSummaryResponse response = insightsService.getInsightsSummary(user, month);

        assertEquals(month, response.month());
        assertEquals(BigDecimal.ZERO, response.currentMonthTotal());
        assertEquals(2, response.insights().size());
        assertEquals("No spending recorded", response.insights().getFirst().title());
        assertNull(response.topCategory());
        assertNull(response.largestExpense());
    }

    @Test
    void getInsightsSummaryShouldReturnComparisonsTopCategoryAndLargestExpense() {
        User user = createUser(2L);
        YearMonth month = YearMonth.of(2026, 4);
        Expense largestExpense = createExpense(99L, "Travel", new BigDecimal("500.00"), LocalDate.of(2026, 4, 7), "Cab ride");

        when(expenseRepository.sumAmountByUserIdAndExpenseDateBetween(
                eq(user.getId()),
                eq(LocalDate.of(2026, 4, 1)),
                eq(LocalDate.of(2026, 4, 30))
        )).thenReturn(new BigDecimal("800.00"));
        when(expenseRepository.sumAmountByUserIdAndExpenseDateBetween(
                eq(user.getId()),
                eq(LocalDate.of(2026, 3, 1)),
                eq(LocalDate.of(2026, 3, 31))
        )).thenReturn(new BigDecimal("200.00"));
        when(expenseRepository.findCategorySpendingByUserIdAndExpenseDateBetween(
                eq(user.getId()),
                eq(LocalDate.of(2026, 4, 1)),
                eq(LocalDate.of(2026, 4, 30))
        )).thenReturn(List.of(
                new CategorySpendingResponse(2L, "Travel", new BigDecimal("500.00")),
                new CategorySpendingResponse(1L, "Food", new BigDecimal("300.00"))
        ));
        when(expenseRepository.findTopByUserIdAndExpenseDateBetweenOrderByAmountDescIdDesc(
                eq(user.getId()),
                eq(LocalDate.of(2026, 4, 1)),
                eq(LocalDate.of(2026, 4, 30)),
                any(Pageable.class)
        )).thenReturn(List.of(largestExpense));

        InsightsSummaryResponse response = insightsService.getInsightsSummary(user, month);

        assertEquals(new BigDecimal("800.00"), response.currentMonthTotal());
        assertEquals(new BigDecimal("200.00"), response.previousMonthTotal());
        assertEquals(new BigDecimal("600.00"), response.absoluteChange());
        assertEquals(new BigDecimal("300.00"), response.percentageChange());
        assertEquals("Travel", response.topCategory().categoryName());
        assertEquals(new BigDecimal("62.50"), response.topCategorySharePercentage());
        assertEquals("Cab ride", response.largestExpense().description());
        assertEquals("Spending increased", response.insights().getFirst().title());
    }

    private User createUser(Long id) {
        User user = new User();
        user.setId(id);
        user.setFullName("Insights Tester");
        user.setEmail("insights@test.com");
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private Expense createExpense(
            Long categoryId,
            String categoryName,
            BigDecimal amount,
            LocalDate expenseDate,
            String description
    ) {
        Category category = new Category();
        category.setId(categoryId);
        category.setName(categoryName);

        Expense expense = new Expense();
        expense.setId(100L);
        expense.setCategory(category);
        expense.setAmount(amount);
        expense.setExpenseDate(expenseDate);
        expense.setDescription(description);
        expense.setPaymentMethod(PaymentMethod.UPI);
        return expense;
    }
}

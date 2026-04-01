package com.expensetracker.recurring.dto;

import com.expensetracker.expense.entity.PaymentMethod;
import com.expensetracker.recurring.entity.RecurringExpense;
import com.expensetracker.recurring.entity.RecurringFrequency;

import java.math.BigDecimal;
import java.time.LocalDate;

public record RecurringExpenseResponse(
        Long id,
        Long categoryId,
        String categoryName,
        BigDecimal amount,
        LocalDate startDate,
        LocalDate nextExecutionDate,
        String description,
        PaymentMethod paymentMethod,
        RecurringFrequency frequency,
        boolean active
) {
    public static RecurringExpenseResponse from(RecurringExpense recurringExpense) {
        return new RecurringExpenseResponse(
                recurringExpense.getId(),
                recurringExpense.getCategory().getId(),
                recurringExpense.getCategory().getName(),
                recurringExpense.getAmount(),
                recurringExpense.getStartDate(),
                recurringExpense.getNextExecutionDate(),
                recurringExpense.getDescription(),
                recurringExpense.getPaymentMethod(),
                recurringExpense.getFrequency(),
                recurringExpense.isActive()
        );
    }
}

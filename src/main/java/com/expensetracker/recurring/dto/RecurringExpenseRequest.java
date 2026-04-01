package com.expensetracker.recurring.dto;

import com.expensetracker.expense.entity.PaymentMethod;
import com.expensetracker.recurring.entity.RecurringFrequency;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;
import java.time.LocalDate;

public record RecurringExpenseRequest(
        @NotNull(message = "Category id is required")
        Long categoryId,

        @NotNull(message = "Amount is required")
        @DecimalMin(value = "0.01", message = "Amount must be greater than zero")
        BigDecimal amount,

        @NotNull(message = "Start date is required")
        LocalDate startDate,

        @Size(max = 255, message = "Description must be at most 255 characters")
        String description,

        @NotNull(message = "Payment method is required")
        PaymentMethod paymentMethod,

        @NotNull(message = "Frequency is required")
        RecurringFrequency frequency
) {
}

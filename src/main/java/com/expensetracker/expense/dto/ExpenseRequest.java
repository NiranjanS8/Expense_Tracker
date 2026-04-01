package com.expensetracker.expense.dto;

import com.expensetracker.expense.entity.PaymentMethod;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseRequest(
        Long categoryId,

        @NotNull(message = "Amount is required")
        @DecimalMin(value = "0.01", message = "Amount must be greater than zero")
        BigDecimal amount,

        @NotNull(message = "Expense date is required")
        LocalDate expenseDate,

        @Size(max = 255, message = "Description must be at most 255 characters")
        String description,

        @NotNull(message = "Payment method is required")
        PaymentMethod paymentMethod
) {
}

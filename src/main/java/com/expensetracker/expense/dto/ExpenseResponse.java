package com.expensetracker.expense.dto;

import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.entity.PaymentMethod;
import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseResponse(
        Long id,
        Long categoryId,
        String categoryName,
        BigDecimal amount,
        LocalDate expenseDate,
        String description,
        PaymentMethod paymentMethod
) {
    public static ExpenseResponse from(Expense expense) {
        return new ExpenseResponse(
                expense.getId(),
                expense.getCategory().getId(),
                expense.getCategory().getName(),
                expense.getAmount(),
                expense.getExpenseDate(),
                expense.getDescription(),
                expense.getPaymentMethod()
        );
    }
}

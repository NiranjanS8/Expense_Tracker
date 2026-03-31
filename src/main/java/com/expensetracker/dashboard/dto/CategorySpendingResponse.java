package com.expensetracker.dashboard.dto;

import java.math.BigDecimal;

public record CategorySpendingResponse(
        Long categoryId,
        String categoryName,
        BigDecimal totalAmount
) {
}

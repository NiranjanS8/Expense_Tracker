package com.expensetracker.dashboard.dto;

import java.math.BigDecimal;
import java.time.YearMonth;

public record MonthlyTrendPointResponse(
        YearMonth month,
        BigDecimal totalAmount
) {
}

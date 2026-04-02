package com.expensetracker.goals.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

public record GoalResponse(
        Long id,
        String name,
        BigDecimal targetAmount,
        BigDecimal currentAmount,
        BigDecimal remainingAmount,
        BigDecimal progressPercentage,
        BigDecimal requiredMonthlyContribution,
        LocalDate targetDate,
        GoalStatus status
) {
}

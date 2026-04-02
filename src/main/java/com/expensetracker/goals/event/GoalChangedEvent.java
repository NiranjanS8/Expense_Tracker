package com.expensetracker.goals.event;

import java.math.BigDecimal;
import java.time.LocalDate;

public record GoalChangedEvent(
        Long goalId,
        Long userId,
        String name,
        BigDecimal targetAmount,
        BigDecimal currentAmount,
        LocalDate targetDate,
        GoalChangeType changeType
) {
}

package com.expensetracker.export.dto;

import com.expensetracker.export.entity.ExpenseExportJobType;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.LocalDate;

public record ExpenseExportJobRequest(
        @NotNull(message = "type is required") ExpenseExportJobType type,
        String sortBy,
        String sortDir,
        String search,
        Long categoryId,
        LocalDate startDate,
        LocalDate endDate,
        @DecimalMin(value = "0.0", inclusive = true, message = "minAmount must be zero or greater") BigDecimal minAmount,
        @DecimalMin(value = "0.0", inclusive = true, message = "maxAmount must be zero or greater") BigDecimal maxAmount
) {
}

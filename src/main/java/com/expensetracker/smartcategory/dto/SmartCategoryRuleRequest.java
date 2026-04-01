package com.expensetracker.smartcategory.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record SmartCategoryRuleRequest(
        @NotBlank(message = "Keyword is required")
        @Size(max = 100, message = "Keyword must be at most 100 characters")
        String keyword,

        @NotNull(message = "Category id is required")
        Long categoryId,

        @NotNull(message = "active is required")
        Boolean active
) {
}

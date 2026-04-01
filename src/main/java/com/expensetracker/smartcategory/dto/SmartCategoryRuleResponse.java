package com.expensetracker.smartcategory.dto;

import com.expensetracker.smartcategory.entity.SmartCategoryRule;

public record SmartCategoryRuleResponse(
        Long id,
        String keyword,
        Long categoryId,
        String categoryName,
        boolean active
) {
    public static SmartCategoryRuleResponse from(SmartCategoryRule rule) {
        return new SmartCategoryRuleResponse(
                rule.getId(),
                rule.getKeyword(),
                rule.getCategory().getId(),
                rule.getCategory().getName(),
                rule.isActive()
        );
    }
}

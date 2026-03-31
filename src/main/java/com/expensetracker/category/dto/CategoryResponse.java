package com.expensetracker.category.dto;

import com.expensetracker.category.entity.Category;

public record CategoryResponse(
        Long id,
        String name,
        boolean systemDefined
) {
    public static CategoryResponse from(Category category) {
        return new CategoryResponse(
                category.getId(),
                category.getName(),
                category.isSystemDefined()
        );
    }
}

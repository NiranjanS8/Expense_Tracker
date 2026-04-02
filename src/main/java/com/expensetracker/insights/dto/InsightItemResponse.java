package com.expensetracker.insights.dto;

public record InsightItemResponse(
        String type,
        String title,
        String message
) {
}

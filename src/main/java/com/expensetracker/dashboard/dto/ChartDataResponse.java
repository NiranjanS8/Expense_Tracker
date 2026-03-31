package com.expensetracker.dashboard.dto;

import java.util.List;

public record ChartDataResponse(
        List<CategorySpendingResponse> pieChart,
        List<CategorySpendingResponse> barChart,
        List<MonthlyTrendPointResponse> lineChart
) {
}

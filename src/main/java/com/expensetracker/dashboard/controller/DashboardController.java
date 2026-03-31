package com.expensetracker.dashboard.controller;

import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.dashboard.dto.ChartDataResponse;
import com.expensetracker.dashboard.dto.DashboardSummaryResponse;
import com.expensetracker.dashboard.dto.MonthlyTrendPointResponse;
import com.expensetracker.dashboard.service.DashboardService;
import com.expensetracker.user.entity.User;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.YearMonth;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
@RequestMapping("/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    @GetMapping("/summary")
    public DashboardSummaryResponse getSummary(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month,
            @RequestParam(defaultValue = "5") @Min(value = 1, message = "recentLimit must be at least 1")
            @Max(value = 20, message = "recentLimit must be at most 20") int recentLimit
    ) {
        return dashboardService.getSummary(user, resolveMonth(month), recentLimit);
    }

    @GetMapping("/categories")
    public List<CategorySpendingResponse> getCategoryInsights(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month
    ) {
        return dashboardService.getCategoryInsights(user, resolveMonth(month));
    }

    @GetMapping("/trends")
    public List<MonthlyTrendPointResponse> getMonthlyTrends(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "6") @Min(value = 1, message = "months must be at least 1")
            @Max(value = 24, message = "months must be at most 24") int months
    ) {
        return dashboardService.getMonthlyTrends(user, months);
    }

    @GetMapping("/charts")
    public ChartDataResponse getChartData(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month,
            @RequestParam(defaultValue = "6") @Min(value = 1, message = "months must be at least 1")
            @Max(value = 24, message = "months must be at most 24") int months
    ) {
        return dashboardService.getChartData(user, resolveMonth(month), months);
    }

    private YearMonth resolveMonth(YearMonth month) {
        return month == null ? YearMonth.now() : month;
    }
}

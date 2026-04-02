package com.expensetracker.insights.controller;

import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.insights.dto.InsightsSummaryResponse;
import com.expensetracker.insights.service.InsightsService;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.YearMonth;

@RestController
@RequestMapping("/insights")
@RequiredArgsConstructor
public class InsightsController {

    private final InsightsService insightsService;

    @GetMapping("/summary")
    public InsightsSummaryResponse getSummary(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month
    ) {
        YearMonth requestedMonth = month == null ? YearMonth.now() : month;
        if (requestedMonth.isAfter(YearMonth.now())) {
            throw new BadRequestException("Insights cannot be generated for future months");
        }

        return insightsService.getInsightsSummary(user, requestedMonth);
    }
}

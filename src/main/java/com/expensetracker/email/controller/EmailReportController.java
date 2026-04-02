package com.expensetracker.email.controller;

import com.expensetracker.email.dto.EmailReportPreferenceRequest;
import com.expensetracker.email.dto.EmailReportPreferenceResponse;
import com.expensetracker.email.dto.EmailReportSendResponse;
import com.expensetracker.email.service.EmailReportService;
import com.expensetracker.security.RateLimitService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.YearMonth;

@RestController
@RequestMapping("/email-reports")
@RequiredArgsConstructor
public class EmailReportController {

    private final EmailReportService emailReportService;
    private final RateLimitService rateLimitService;

    @GetMapping("/preference")
    public EmailReportPreferenceResponse getPreference(@AuthenticationPrincipal User user) {
        return emailReportService.getPreference(user);
    }

    @PutMapping("/preference")
    public EmailReportPreferenceResponse updatePreference(
            @Valid @RequestBody EmailReportPreferenceRequest request,
            @AuthenticationPrincipal User user
    ) {
        return emailReportService.upsertPreference(request, user);
    }

    @PostMapping("/send")
    public EmailReportSendResponse sendManualReport(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM") YearMonth month
    ) {
        rateLimitService.checkEmailSendRateLimit(user);
        return emailReportService.sendManualReport(user, month);
    }
}

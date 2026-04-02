package com.expensetracker.email.dto;

import java.time.YearMonth;

public record EmailReportSendResponse(
        String email,
        YearMonth month,
        boolean sent,
        String message
) {
}

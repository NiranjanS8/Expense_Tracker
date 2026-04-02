package com.expensetracker.email.dto;

import com.expensetracker.email.entity.EmailReportPreference;

public record EmailReportPreferenceResponse(
        Long id,
        String email,
        boolean enabled
) {
    public static EmailReportPreferenceResponse from(EmailReportPreference preference) {
        return new EmailReportPreferenceResponse(
                preference.getId(),
                preference.getEmail(),
                preference.isEnabled()
        );
    }
}

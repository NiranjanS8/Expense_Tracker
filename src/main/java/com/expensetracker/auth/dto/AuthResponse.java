package com.expensetracker.auth.dto;

import com.expensetracker.user.dto.UserProfileResponse;

public record AuthResponse(
        String accessToken,
        String tokenType,
        UserProfileResponse user
) {
}

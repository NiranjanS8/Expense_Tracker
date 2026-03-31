package com.expensetracker.user.dto;

import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;

public record UserProfileResponse(
        Long id,
        String fullName,
        String email,
        Role role
) {
    public static UserProfileResponse from(User user) {
        return new UserProfileResponse(
                user.getId(),
                user.getFullName(),
                user.getEmail(),
                user.getRole()
        );
    }
}

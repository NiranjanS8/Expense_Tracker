package com.expensetracker.user.service;

import com.expensetracker.user.dto.UserProfileResponse;
import com.expensetracker.user.entity.User;
import org.springframework.stereotype.Service;

@Service
public class UserService {

    public UserProfileResponse getCurrentUserProfile(User user) {
        return UserProfileResponse.from(user);
    }
}

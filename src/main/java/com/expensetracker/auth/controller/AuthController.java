package com.expensetracker.auth.controller;

import com.expensetracker.auth.dto.AuthResponse;
import com.expensetracker.auth.dto.LoginRequest;
import com.expensetracker.auth.dto.RegisterRequest;
import com.expensetracker.observability.ObservabilityMetricsService;
import com.expensetracker.auth.service.AuthService;
import com.expensetracker.security.RateLimitService;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
@Tag(name = "Authentication", description = "Registration and login endpoints")
@SecurityRequirements
public class AuthController {

    private final AuthService authService;
    private final ObservabilityMetricsService observabilityMetricsService;
    private final RateLimitService rateLimitService;

    @PostMapping("/register")
    @ResponseStatus(HttpStatus.CREATED)
    public AuthResponse register(@Valid @RequestBody RegisterRequest request, HttpServletRequest httpServletRequest) {
        long startTime = System.nanoTime();
        rateLimitService.checkRegisterRateLimit(httpServletRequest);
        try {
            AuthResponse response = authService.register(request);
            observabilityMetricsService.recordAuthRequest("register", "success", System.nanoTime() - startTime);
            return response;
        } catch (RuntimeException exception) {
            observabilityMetricsService.recordAuthRequest("register", "failure", System.nanoTime() - startTime);
            throw exception;
        }
    }

    @PostMapping("/login")
    public AuthResponse login(@Valid @RequestBody LoginRequest request, HttpServletRequest httpServletRequest) {
        long startTime = System.nanoTime();
        rateLimitService.checkLoginRateLimit(httpServletRequest);
        try {
            AuthResponse response = authService.login(request);
            observabilityMetricsService.recordAuthRequest("login", "success", System.nanoTime() - startTime);
            return response;
        } catch (RuntimeException exception) {
            observabilityMetricsService.recordAuthRequest("login", "failure", System.nanoTime() - startTime);
            throw exception;
        }
    }
}

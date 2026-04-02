package com.expensetracker.security;

import com.expensetracker.common.exception.TooManyRequestsException;
import com.expensetracker.user.entity.User;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

@Service
public class RateLimitService {

    private static final int LOGIN_MAX_ATTEMPTS = 5;
    private static final int REGISTER_MAX_ATTEMPTS = 3;
    private static final int EXPORT_JOB_MAX_ATTEMPTS = 5;
    private static final int EMAIL_SEND_MAX_ATTEMPTS = 2;
    private static final int RECURRING_GENERATION_MAX_ATTEMPTS = 10;

    private static final Duration LOGIN_WINDOW = Duration.ofMinutes(1);
    private static final Duration REGISTER_WINDOW = Duration.ofHours(1);
    private static final Duration EXPORT_JOB_WINDOW = Duration.ofMinutes(10);
    private static final Duration EMAIL_SEND_WINDOW = Duration.ofHours(1);
    private static final Duration RECURRING_GENERATION_WINDOW = Duration.ofHours(1);

    private final Map<String, WindowCounter> counters = new ConcurrentHashMap<>();

    public void checkLoginRateLimit(HttpServletRequest request) {
        checkRateLimit(
                "auth:login:" + resolveClientIp(request),
                LOGIN_MAX_ATTEMPTS,
                LOGIN_WINDOW,
                "Too many login attempts. Please try again later."
        );
    }

    public void checkRegisterRateLimit(HttpServletRequest request) {
        checkRateLimit(
                "auth:register:" + resolveClientIp(request),
                REGISTER_MAX_ATTEMPTS,
                REGISTER_WINDOW,
                "Too many registration attempts. Please try again later."
        );
    }

    public void checkExportJobRateLimit(User user) {
        checkRateLimit(
                "exports:jobs:user:" + user.getId(),
                EXPORT_JOB_MAX_ATTEMPTS,
                EXPORT_JOB_WINDOW,
                "Too many export job requests. Please try again later."
        );
    }

    public void checkEmailSendRateLimit(User user) {
        checkRateLimit(
                "email:send:user:" + user.getId(),
                EMAIL_SEND_MAX_ATTEMPTS,
                EMAIL_SEND_WINDOW,
                "Too many email report requests. Please try again later."
        );
    }

    public void checkRecurringGenerationRateLimit(User user) {
        checkRateLimit(
                "recurring:generate:user:" + user.getId(),
                RECURRING_GENERATION_MAX_ATTEMPTS,
                RECURRING_GENERATION_WINDOW,
                "Too many recurring generation requests. Please try again later."
        );
    }

    public void clearAll() {
        counters.clear();
    }

    private void checkRateLimit(String key, int maxAttempts, Duration window, String message) {
        Instant now = Instant.now();

        WindowCounter counter = counters.compute(key, (ignored, existingCounter) -> {
            if (existingCounter == null || existingCounter.windowEnd().isBefore(now)) {
                return new WindowCounter(1, now.plus(window));
            }

            return new WindowCounter(existingCounter.count() + 1, existingCounter.windowEnd());
        });

        if (counter.count() > maxAttempts) {
            long retryAfterSeconds = Math.max(1, Duration.between(now, counter.windowEnd()).getSeconds());
            throw new TooManyRequestsException(message, retryAfterSeconds);
        }
    }

    private String resolveClientIp(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return forwardedFor.split(",")[0].trim();
        }

        String remoteAddress = request.getRemoteAddr();
        return remoteAddress == null || remoteAddress.isBlank() ? "unknown" : remoteAddress;
    }

    private record WindowCounter(int count, Instant windowEnd) {
    }
}

package com.expensetracker.email.service;

import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import com.expensetracker.dashboard.dto.DashboardSummaryResponse;
import com.expensetracker.dashboard.service.DashboardService;
import com.expensetracker.email.config.EmailReportProperties;
import com.expensetracker.email.dto.EmailReportPreferenceRequest;
import com.expensetracker.email.dto.EmailReportPreferenceResponse;
import com.expensetracker.email.dto.EmailReportSendResponse;
import com.expensetracker.email.entity.EmailReportPreference;
import com.expensetracker.email.repository.EmailReportPreferenceRepository;
import com.expensetracker.job.service.JobLockService;
import com.expensetracker.insights.dto.InsightItemResponse;
import com.expensetracker.insights.dto.InsightsSummaryResponse;
import com.expensetracker.insights.service.InsightsService;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import com.expensetracker.user.repository.UserRepository;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.util.List;
import java.util.Optional;
import java.util.Properties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mail.MailSendException;
import org.springframework.mail.javamail.JavaMailSender;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class EmailReportServiceTest {

    @Mock
    private EmailReportPreferenceRepository preferenceRepository;

    @Mock
    private DashboardService dashboardService;

    @Mock
    private InsightsService insightsService;

    @Mock
    private EmailReportProperties emailReportProperties;

    @Mock
    private UserRepository userRepository;

    @Mock
    private JavaMailSender javaMailSender;

    @Mock
    private JobLockService jobLockService;

    @Test
    void upsertPreferenceShouldNormalizeEmailAndPersistState() {
        EmailReportService emailReportService = createService(Optional.empty());
        User user = createUser(1L, "Test User", "user@example.com");
        EmailReportPreference savedPreference = new EmailReportPreference();
        savedPreference.setId(50L);
        savedPreference.setUser(user);
        savedPreference.setEmail("reports@example.com");
        savedPreference.setEnabled(true);

        when(preferenceRepository.findByUserId(user.getId())).thenReturn(Optional.empty());
        when(preferenceRepository.save(any(EmailReportPreference.class))).thenReturn(savedPreference);

        EmailReportPreferenceResponse response = emailReportService.upsertPreference(
                new EmailReportPreferenceRequest(" Reports@Example.com ", true),
                user
        );

        assertEquals(50L, response.id());
        assertEquals("reports@example.com", response.email());
        assertTrue(response.enabled());
        verify(preferenceRepository).save(any(EmailReportPreference.class));
    }

    @Test
    void sendManualReportShouldReturnLoggedOnlyWhenMailSenderIsMissing() {
        EmailReportService emailReportService = createService(Optional.empty());
        User user = createUser(2L, "Feature Tester", "feature@example.com");
        EmailReportPreference preference = createPreference(user, "reports@example.com", true);
        YearMonth month = YearMonth.of(2026, 3);

        when(preferenceRepository.findByUserId(user.getId())).thenReturn(Optional.of(preference));
        when(dashboardService.getSummary(user, month, 5)).thenReturn(
                new DashboardSummaryResponse(month, new BigDecimal("250.00"), 1, List.of())
        );
        when(insightsService.getInsightsSummary(user, month)).thenReturn(
                new InsightsSummaryResponse(
                        month,
                        new BigDecimal("250.00"),
                        BigDecimal.ZERO,
                        new BigDecimal("250.00"),
                        BigDecimal.ZERO,
                        new BigDecimal("8.06"),
                        new CategorySpendingResponse(1L, "Food", new BigDecimal("250.00")),
                        new BigDecimal("100.00"),
                        null,
                        List.of(new InsightItemResponse("comparison", "Fresh baseline", "Baseline created."))
                )
        );

        EmailReportSendResponse response = emailReportService.sendManualReport(user, month);

        assertEquals("reports@example.com", response.email());
        assertFalse(response.sent());
        assertEquals("Mail sender is not configured. Report was generated and logged only.", response.message());
    }

    @Test
    void sendManualReportShouldReturnFailureWhenMailSenderThrows() {
        EmailReportService emailReportService = createService(Optional.of(javaMailSender));
        User user = createUser(3L, "Mailer", "mailer@example.com");
        EmailReportPreference preference = createPreference(user, "mailer-reports@example.com", true);
        YearMonth month = YearMonth.of(2026, 3);
        MimeMessage mimeMessage = new MimeMessage(Session.getInstance(new Properties()));

        when(preferenceRepository.findByUserId(user.getId())).thenReturn(Optional.of(preference));
        when(dashboardService.getSummary(user, month, 5)).thenReturn(
                new DashboardSummaryResponse(month, new BigDecimal("500.00"), 2, List.of())
        );
        when(insightsService.getInsightsSummary(user, month)).thenReturn(
                new InsightsSummaryResponse(
                        month,
                        new BigDecimal("500.00"),
                        new BigDecimal("400.00"),
                        new BigDecimal("100.00"),
                        new BigDecimal("25.00"),
                        new BigDecimal("16.13"),
                        null,
                        BigDecimal.ZERO,
                        null,
                        List.of(new InsightItemResponse("comparison", "Spending increased", "Spending increased."))
                )
        );
        when(emailReportProperties.from()).thenReturn("no-reply@example.com");
        when(javaMailSender.createMimeMessage()).thenReturn(mimeMessage);
        org.mockito.Mockito.doThrow(new MailSendException("SMTP failure")).when(javaMailSender).send(mimeMessage);

        EmailReportSendResponse response = emailReportService.sendManualReport(user, month);

        assertEquals("mailer-reports@example.com", response.email());
        assertFalse(response.sent());
        assertEquals("Failed to send email report.", response.message());
    }

    private EmailReportService createService(Optional<JavaMailSender> mailSender) {
        return new EmailReportService(
                preferenceRepository,
                dashboardService,
                insightsService,
                emailReportProperties,
                userRepository,
                mailSender,
                jobLockService
        );
    }

    private User createUser(Long id, String fullName, String email) {
        User user = new User();
        user.setId(id);
        user.setFullName(fullName);
        user.setEmail(email);
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private EmailReportPreference createPreference(User user, String email, boolean enabled) {
        EmailReportPreference preference = new EmailReportPreference();
        preference.setId(20L);
        preference.setUser(user);
        preference.setEmail(email);
        preference.setEnabled(enabled);
        return preference;
    }
}

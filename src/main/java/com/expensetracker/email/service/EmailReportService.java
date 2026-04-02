package com.expensetracker.email.service;

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
import com.expensetracker.observability.ObservabilityMetricsService;
import com.expensetracker.user.entity.User;
import com.expensetracker.user.repository.UserRepository;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.mail.MailException;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.YearMonth;
import java.time.Duration;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class EmailReportService {

    private static final Logger logger = LoggerFactory.getLogger(EmailReportService.class);
    private static final String EMAIL_REPORT_JOB_LOCK = "email-report-scheduler";
    private static final Duration EMAIL_REPORT_JOB_MAX_LOCK_DURATION = Duration.ofMinutes(30);

    private final EmailReportPreferenceRepository preferenceRepository;
    private final DashboardService dashboardService;
    private final InsightsService insightsService;
    private final EmailReportProperties emailReportProperties;
    private final UserRepository userRepository;
    private final Optional<JavaMailSender> javaMailSender;
    private final JobLockService jobLockService;
    private final ObservabilityMetricsService observabilityMetricsService;

    @Transactional(readOnly = true)
    public EmailReportPreferenceResponse getPreference(User user) {
        return preferenceRepository.findByUserId(user.getId())
                .map(EmailReportPreferenceResponse::from)
                .orElseGet(() -> new EmailReportPreferenceResponse(null, user.getEmail(), false));
    }

    @Transactional
    public EmailReportPreferenceResponse upsertPreference(EmailReportPreferenceRequest request, User user) {
        EmailReportPreference preference = preferenceRepository.findByUserId(user.getId())
                .orElseGet(() -> {
                    EmailReportPreference createdPreference = new EmailReportPreference();
                    createdPreference.setUser(user);
                    return createdPreference;
                });

        preference.setEmail(request.email().trim().toLowerCase());
        preference.setEnabled(request.enabled());
        return EmailReportPreferenceResponse.from(preferenceRepository.save(preference));
    }

    @Transactional(readOnly = true)
    public EmailReportSendResponse sendManualReport(User user, YearMonth month) {
        return sendReport(user, resolveMonth(month), "manual");
    }

    @Scheduled(cron = "${app.email.reports.cron:0 0 9 1 * *}")
    public void sendScheduledReports() {
        if (!emailReportProperties.enabled()) {
            return;
        }

        jobLockService.runWithLock(
                EMAIL_REPORT_JOB_LOCK,
                EMAIL_REPORT_JOB_MAX_LOCK_DURATION,
                "email-job",
                this::runScheduledReports
        );
    }

    @Transactional(readOnly = true)
    void runScheduledReports() {
        YearMonth reportMonth = YearMonth.now().minusMonths(1);
        int processed = 0;
        int sent = 0;
        int skipped = 0;
        int failed = 0;
        long startTime = System.nanoTime();

        for (EmailReportPreference preference : preferenceRepository.findAllByEnabledTrue()) {
            try {
                processed++;
                Optional<User> userOptional = userRepository.findById(preference.getUser().getId());
                if (userOptional.isPresent()) {
                    EmailReportSendResponse response = sendReport(userOptional.orElseThrow(), reportMonth, "scheduled");
                    if (response.sent()) {
                        sent++;
                    } else if ("Failed to send email report.".equals(response.message())) {
                        failed++;
                    } else {
                        skipped++;
                    }
                } else {
                    skipped++;
                }
            } catch (RuntimeException exception) {
                failed++;
                logger.error("event=email_report_scheduled_failure preferenceId={} month={} error={}",
                        preference.getId(), reportMonth, exception.getMessage(), exception);
            }
        }

        logger.info(
                "event=email_report_batch_completed month={} processed={} sent={} skipped={} failed={} durationMs={}",
                reportMonth,
                processed,
                sent,
                skipped,
                failed,
                (System.nanoTime() - startTime) / 1_000_000
        );
    }

    private EmailReportSendResponse sendReport(User user, YearMonth month, String trigger) {
        long startTime = System.nanoTime();
        EmailReportPreference preference = preferenceRepository.findByUserId(user.getId())
                .orElse(null);

        if (preference == null || !preference.isEnabled()) {
            observabilityMetricsService.recordEmailSend(trigger, "disabled", System.nanoTime() - startTime);
            return new EmailReportSendResponse(
                    user.getEmail(),
                    month,
                    false,
                    "Email reports are disabled for this user."
            );
        }

        String subject = "Expense Tracker Monthly Summary - " + month;
        String body = buildEmailBody(user, month);

        if (javaMailSender.isEmpty()) {
            observabilityMetricsService.recordEmailSend(trigger, "logged_only", System.nanoTime() - startTime);
            logger.info(
                    "event=email_report_logged_only trigger={} userId={} email={} month={}",
                    trigger,
                    user.getId(),
                    user.getEmail(),
                    month
            );
            logger.info(body);
            return new EmailReportSendResponse(
                    preference.getEmail(),
                    month,
                    false,
                    "Mail sender is not configured. Report was generated and logged only."
            );
        }

        try {
            MimeMessage mimeMessage = javaMailSender.get().createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(mimeMessage, false, "UTF-8");
            helper.setFrom(emailReportProperties.from());
            helper.setTo(preference.getEmail());
            helper.setSubject(subject);
            helper.setText(body, false);
            javaMailSender.get().send(mimeMessage);
            observabilityMetricsService.recordEmailSend(trigger, "success", System.nanoTime() - startTime);
            logger.info(
                    "event=email_report_sent trigger={} userId={} email={} month={} durationMs={}",
                    trigger,
                    user.getId(),
                    preference.getEmail(),
                    month,
                    (System.nanoTime() - startTime) / 1_000_000
            );

            return new EmailReportSendResponse(preference.getEmail(), month, true, "Email report sent successfully.");
        } catch (MessagingException | MailException exception) {
            observabilityMetricsService.recordEmailSend(trigger, "failure", System.nanoTime() - startTime);
            logger.error(
                    "event=email_report_failed trigger={} userId={} email={} month={} error={}",
                    trigger,
                    user.getId(),
                    preference.getEmail(),
                    month,
                    exception.getMessage(),
                    exception
            );
            return new EmailReportSendResponse(
                    preference.getEmail(),
                    month,
                    false,
                    "Failed to send email report."
            );
        }
    }

    private String buildEmailBody(User user, YearMonth month) {
        DashboardSummaryResponse dashboardSummary = dashboardService.getSummary(user, month, 5);
        InsightsSummaryResponse insightsSummary = insightsService.getInsightsSummary(user, month);
        String greetingName = resolveGreetingName(user);

        StringBuilder builder = new StringBuilder();
        builder.append("Monthly Expense Summary for ").append(month).append("\n\n");
        builder.append("Hello ").append(greetingName).append(",\n\n");
        builder.append("Total spending: ").append(dashboardSummary.monthlyTotal()).append("\n");
        builder.append("Transactions: ").append(dashboardSummary.transactionCount()).append("\n");
        if (insightsSummary.topCategory() != null) {
            builder.append("Top category: ")
                    .append(insightsSummary.topCategory().categoryName())
                    .append(" (")
                    .append(insightsSummary.topCategory().totalAmount())
                    .append(")\n");
        }
        builder.append("Average daily spend: ").append(insightsSummary.averageDailySpend()).append("\n");
        builder.append("Month-over-month change: ").append(insightsSummary.percentageChange()).append("%\n\n");

        builder.append("Insights:\n");
        for (InsightItemResponse insight : insightsSummary.insights()) {
            builder.append("- ").append(insight.title()).append(": ").append(insight.message()).append("\n");
        }

        return builder.toString();
    }

    private YearMonth resolveMonth(YearMonth month) {
        return month == null ? YearMonth.now().minusMonths(1) : month;
    }

    private String resolveGreetingName(User user) {
        if (user.getFullName() != null && !user.getFullName().trim().isEmpty()) {
            return user.getFullName().trim();
        }

        return user.getEmail();
    }
}

package com.expensetracker.features;

import com.expensetracker.export.service.ExpenseExportJobService;
import com.expensetracker.security.RateLimitService;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDate;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
class FeatureIntegrationTest {

    private MockMvc mockMvc;

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ExpenseExportJobService expenseExportJobService;

    @Autowired
    private RateLimitService rateLimitService;

    @BeforeEach
    void setUp() {
        rateLimitService.clearAll();
        jdbcTemplate.execute("DELETE FROM expenses");
        jdbcTemplate.execute("DELETE FROM expense_export_jobs");
        jdbcTemplate.execute("DELETE FROM recurring_expenses");
        jdbcTemplate.execute("DELETE FROM smart_category_rules");
        jdbcTemplate.execute("DELETE FROM goals");
        jdbcTemplate.execute("DELETE FROM email_report_preferences");
        jdbcTemplate.execute("DELETE FROM budgets");
        jdbcTemplate.execute("DELETE FROM categories");
        jdbcTemplate.execute("DELETE FROM job_locks");
        jdbcTemplate.execute("DELETE FROM users");
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext)
                .apply(SecurityMockMvcConfigurers.springSecurity())
                .build();
    }

    @Test
    void recurringExpensesShouldGenerateIdempotentlyAndRespectInactiveStatus() throws Exception {
        String token = registerAndLogin("recurring@example.com");
        long categoryId = createCategory(token, "Utilities");

        String recurringResponse = mockMvc.perform(post("/api/recurring-expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": 1200.00,
                                  "startDate": "2026-03-05",
                                  "description": "Monthly internet bill",
                                  "paymentMethod": "BANK_TRANSFER",
                                  "frequency": "MONTHLY"
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.active", equalTo(true)))
                .andExpect(jsonPath("$.nextExecutionDate", equalTo("2026-03-05")))
                .andReturn()
                .getResponse()
                .getContentAsString();

        long recurringExpenseId = extractLongField(recurringResponse, "id");

        mockMvc.perform(post("/api/recurring-expenses/generate")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("runDate", "2026-03-05"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recurringRulesProcessed", equalTo(1)))
                .andExpect(jsonPath("$.expensesGenerated", equalTo(1)));

        mockMvc.perform(post("/api/recurring-expenses/generate")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("runDate", "2026-03-05"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recurringRulesProcessed", equalTo(0)))
                .andExpect(jsonPath("$.expensesGenerated", equalTo(0)));

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("search", "internet"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalElements", equalTo(1)))
                .andExpect(jsonPath("$.content", hasSize(1)));

        mockMvc.perform(patch("/api/recurring-expenses/" + recurringExpenseId + "/status")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "active": false
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active", equalTo(false)));

        mockMvc.perform(post("/api/recurring-expenses/generate")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("runDate", "2026-04-10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recurringRulesProcessed", equalTo(0)))
                .andExpect(jsonPath("$.expensesGenerated", equalTo(0)));
    }

    @Test
    void insightsShouldReturnComparisonsAndRejectFutureMonths() throws Exception {
        String token = registerAndLogin("insights@example.com");
        long foodCategoryId = createCategory(token, "Food");
        long travelCategoryId = createCategory(token, "Travel");

        createExpense(token, foodCategoryId, "March groceries", "2026-03-10", "200.00", "CARD");
        createExpense(token, foodCategoryId, "April groceries", "2026-04-01", "300.00", "CARD");
        createExpense(token, travelCategoryId, "Cab ride", "2026-04-07", "500.00", "UPI");

        mockMvc.perform(get("/api/insights/summary")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("month", "2026-04"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.month", equalTo("2026-04")))
                .andExpect(jsonPath("$.currentMonthTotal", equalTo(800.00)))
                .andExpect(jsonPath("$.previousMonthTotal", equalTo(200.00)))
                .andExpect(jsonPath("$.absoluteChange", equalTo(600.00)))
                .andExpect(jsonPath("$.percentageChange", equalTo(300.00)))
                .andExpect(jsonPath("$.topCategory.categoryName", equalTo("Travel")))
                .andExpect(jsonPath("$.largestExpense.description", equalTo("Cab ride")))
                .andExpect(jsonPath("$.insights", hasSize(greaterThan(0))));

        mockMvc.perform(get("/api/insights/summary")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("month", "2026-05"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Insights cannot be generated for future months")));
    }

    @Test
    void asyncExportJobsShouldCompleteAndReturnDownloadableFiles() throws Exception {
        String token = registerAndLogin("async-export@example.com");
        long categoryId = createCategory(token, "Bills");

        createExpense(token, categoryId, "Water bill", "2026-04-02", "450.00", "BANK_TRANSFER");

        String jobResponse = mockMvc.perform(post("/api/exports/jobs")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "type": "CSV",
                                  "search": "Water"
                                }
                                """))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.status", equalTo("PENDING")))
                .andExpect(jsonPath("$.downloadReady", equalTo(false)))
                .andReturn()
                .getResponse()
                .getContentAsString();

        long jobId = extractLongField(jobResponse, "id");
        expenseExportJobService.processPendingJobs();

        mockMvc.perform(get("/api/exports/jobs/" + jobId)
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("COMPLETED")))
                .andExpect(jsonPath("$.downloadReady", equalTo(true)))
                .andExpect(jsonPath("$.fileName", containsString(".csv")));

        String csv = mockMvc.perform(get("/api/exports/jobs/" + jobId + "/download")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token)))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.CONTENT_DISPOSITION, containsString(".csv")))
                .andExpect(content().contentType("text/csv"))
                .andReturn()
                .getResponse()
                .getContentAsString(StandardCharsets.UTF_8);

        org.junit.jupiter.api.Assertions.assertTrue(csv.contains("Water bill"));
    }

    @Test
    void removedSynchronousExportEndpointsShouldReturnGone() throws Exception {
        String token = registerAndLogin("exportlimit@example.com");

        mockMvc.perform(get("/api/exports/expenses/csv")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token)))
                .andExpect(status().isGone())
                .andExpect(jsonPath("$.message",
                        equalTo("Synchronous export endpoints were removed. Create an async export job at /exports/jobs instead.")));

        mockMvc.perform(get("/api/exports/expenses/pdf")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token)))
                .andExpect(status().isGone())
                .andExpect(jsonPath("$.message",
                        equalTo("Synchronous export endpoints were removed. Create an async export job at /exports/jobs instead.")));
    }

    @Test
    void asyncExportJobsShouldMoveToFailedWhenGenerationFails() throws Exception {
        String token = registerAndLogin("async-export-fail@example.com");
        long categoryId = createCategory(token, "Bulk");
        long userId = findUserIdByEmail("async-export-fail@example.com");
        Instant now = Instant.now();
        Timestamp timestamp = Timestamp.from(now);

        for (int index = 0; index < 5001; index++) {
            jdbcTemplate.update(
                    """
                    INSERT INTO expenses (
                        user_id,
                        category_id,
                        recurring_expense_id,
                        amount,
                        expense_date,
                        description,
                        payment_method,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    userId,
                    categoryId,
                    null,
                    10.00,
                    LocalDate.of(2026, 4, 1),
                    "Bulk expense " + index,
                    "CARD",
                    timestamp,
                    timestamp
            );
        }

        String jobResponse = mockMvc.perform(post("/api/exports/jobs")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "type": "CSV"
                                }
                                """))
                .andExpect(status().isAccepted())
                .andReturn()
                .getResponse()
                .getContentAsString();

        long jobId = extractLongField(jobResponse, "id");
        expenseExportJobService.processPendingJobs();

        mockMvc.perform(get("/api/exports/jobs/" + jobId)
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("FAILED")))
                .andExpect(jsonPath("$.downloadReady", equalTo(false)))
                .andExpect(jsonPath("$.errorMessage",
                        equalTo("Export is limited to 5000 expenses. Narrow the filters and try again.")));
    }

    @Test
    void exportJobCreationShouldRateLimitPerUser() throws Exception {
        String token = registerAndLogin("export-rate-limit@example.com");

        for (int attempt = 0; attempt < 5; attempt++) {
            mockMvc.perform(post("/api/exports/jobs")
                            .contextPath("/api")
                            .with(csrf())
                            .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {
                                      "type": "CSV"
                                    }
                                    """))
                    .andExpect(status().isAccepted());
        }

        mockMvc.perform(post("/api/exports/jobs")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "type": "CSV"
                                }
                                """))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.message", equalTo("Too many export job requests. Please try again later.")));
    }

    @Test
    void emailReportsShouldStorePreferenceAndReturnFallbackWhenMailSenderIsMissing() throws Exception {
        String token = registerAndLogin("emailreports@example.com");
        long categoryId = createCategory(token, "Food");

        createExpense(token, categoryId, "Lunch", "2026-03-10", "250.00", "UPI");

        mockMvc.perform(put("/api/email-reports/preference")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "reports@example.com",
                                  "enabled": true
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email", equalTo("reports@example.com")))
                .andExpect(jsonPath("$.enabled", equalTo(true)));

        mockMvc.perform(post("/api/email-reports/send")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("month", "2026-03"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email", equalTo("reports@example.com")))
                .andExpect(jsonPath("$.month", equalTo("2026-03")))
                .andExpect(jsonPath("$.sent", equalTo(false)))
                .andExpect(jsonPath("$.message",
                        equalTo("Mail sender is not configured. Report was generated and logged only.")));
    }

    @Test
    void emailReportSendShouldRateLimitPerUser() throws Exception {
        String token = registerAndLogin("email-rate-limit@example.com");

        mockMvc.perform(put("/api/email-reports/preference")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "ratelimited@example.com",
                                  "enabled": true
                                }
                                """))
                .andExpect(status().isOk());

        for (int attempt = 0; attempt < 2; attempt++) {
            mockMvc.perform(post("/api/email-reports/send")
                            .contextPath("/api")
                            .with(csrf())
                            .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                            .param("month", "2026-03"))
                    .andExpect(status().isOk());
        }

        mockMvc.perform(post("/api/email-reports/send")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("month", "2026-03"))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.message", equalTo("Too many email report requests. Please try again later.")));
    }

    @Test
    void recurringGenerationShouldRateLimitPerUser() throws Exception {
        String token = registerAndLogin("recurring-rate-limit@example.com");

        for (int attempt = 0; attempt < 10; attempt++) {
            mockMvc.perform(post("/api/recurring-expenses/generate")
                            .contextPath("/api")
                            .with(csrf())
                            .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                            .param("runDate", "2026-04-10"))
                    .andExpect(status().isOk());
        }

        mockMvc.perform(post("/api/recurring-expenses/generate")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("runDate", "2026-04-10"))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.message",
                        equalTo("Too many recurring generation requests. Please try again later.")));
    }

    private String registerAndLogin(String email) throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "Feature Tester",
                                  "email": "%s",
                                  "password": "Password@123"
                                }
                                """.formatted(email)))
                .andExpect(status().isCreated());

        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "%s",
                                  "password": "Password@123"
                                }
                                """.formatted(email)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        return extractStringField(loginResponse, "accessToken");
    }

    private long createCategory(String token, String name) throws Exception {
        String response = mockMvc.perform(post("/api/categories")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "%s"
                                }
                                """.formatted(name)))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();

        return extractLongField(response, "id");
    }

    private void createExpense(
            String token,
            long categoryId,
            String description,
            String expenseDate,
            String amount,
            String paymentMethod
    ) throws Exception {
        mockMvc.perform(post("/api/expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": %s,
                                  "expenseDate": "%s",
                                  "description": "%s",
                                  "paymentMethod": "%s"
                                }
                                """.formatted(categoryId, amount, expenseDate, description, paymentMethod)))
                .andExpect(status().isCreated());
    }

    private long findUserIdByEmail(String email) {
        Long userId = jdbcTemplate.queryForObject(
                "SELECT id FROM users WHERE email = ?",
                Long.class,
                email
        );
        if (userId == null) {
            throw new IllegalStateException("User not found for email " + email);
        }
        return userId;
    }

    private String bearerToken(String token) {
        return "Bearer " + token;
    }

    private String extractStringField(String json, String fieldName) {
        String marker = "\"" + fieldName + "\":\"";
        int start = json.indexOf(marker);
        int valueStart = start + marker.length();
        int valueEnd = json.indexOf('"', valueStart);
        return json.substring(valueStart, valueEnd);
    }

    private long extractLongField(String json, String fieldName) {
        String marker = "\"" + fieldName + "\":";
        int start = json.indexOf(marker);
        int valueStart = start + marker.length();
        int valueEnd = json.indexOf(',', valueStart);
        if (valueEnd == -1) {
            valueEnd = json.indexOf('}', valueStart);
        }
        return Long.parseLong(json.substring(valueStart, valueEnd).trim());
    }
}

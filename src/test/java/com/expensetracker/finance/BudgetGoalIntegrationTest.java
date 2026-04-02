package com.expensetracker.finance;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.time.LocalDate;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
class BudgetGoalIntegrationTest {

    private MockMvc mockMvc;

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void setUp() {
        jdbcTemplate.execute("DELETE FROM expenses");
        jdbcTemplate.execute("DELETE FROM recurring_expenses");
        jdbcTemplate.execute("DELETE FROM smart_category_rules");
        jdbcTemplate.execute("DELETE FROM goals");
        jdbcTemplate.execute("DELETE FROM email_report_preferences");
        jdbcTemplate.execute("DELETE FROM budgets");
        jdbcTemplate.execute("DELETE FROM categories");
        jdbcTemplate.execute("DELETE FROM users");
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext)
                .apply(SecurityMockMvcConfigurers.springSecurity())
                .build();
    }

    @Test
    void currentBudgetShouldReturnEmptySummaryWhenNoBudgetExists() throws Exception {
        String token = registerAndLogin("nobudget@example.com");

        mockMvc.perform(get("/api/budgets/current")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").doesNotExist())
                .andExpect(jsonPath("$.budgetAmount", equalTo(0)))
                .andExpect(jsonPath("$.status", equalTo("ON_TRACK")));
    }

    @Test
    void budgetEndpointsShouldCreateUpdateGetAndListBudgetHistory() throws Exception {
        String token = registerAndLogin("budget@example.com");

        mockMvc.perform(post("/api/budgets")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 15000.00,
                                  "budgetMonth": "2026-04"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.budgetAmount", equalTo(15000.00)))
                .andExpect(jsonPath("$.budgetMonth", equalTo("2026-04")));

        mockMvc.perform(put("/api/budgets/2026-04")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 18000.00,
                                  "budgetMonth": "2026-04"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.budgetAmount", equalTo(18000.00)));

        mockMvc.perform(get("/api/budgets/2026-04")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.budgetMonth", equalTo("2026-04")))
                .andExpect(jsonPath("$.budgetAmount", equalTo(18000.00)));

        mockMvc.perform(get("/api/budgets")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("year", "2026"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].budgetMonth", equalTo("2026-04")));
    }

    @Test
    void budgetSummaryShouldCalculateSpentRemainingAndAlerts() throws Exception {
        String token = registerAndLogin("alerts@example.com");
        long categoryId = createCategory(token, "Bills");

        createExpense(token, categoryId, "Electricity bill", "2026-04-02", "900.00", "BANK_TRANSFER");

        mockMvc.perform(post("/api/budgets")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 1000.00,
                                  "budgetMonth": "2026-04"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.spentAmount", equalTo(900.00)))
                .andExpect(jsonPath("$.remainingAmount", equalTo(100.00)))
                .andExpect(jsonPath("$.usagePercentage", equalTo(90.00)))
                .andExpect(jsonPath("$.status", equalTo("CRITICAL")))
                .andExpect(jsonPath("$.alertLevel", equalTo("CRITICAL")))
                .andExpect(jsonPath("$.triggeredThresholds", hasSize(2)));
    }

    @Test
    void budgetUpdateShouldRejectMismatchedMonth() throws Exception {
        String token = registerAndLogin("budgetmismatch@example.com");

        mockMvc.perform(post("/api/budgets")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 5000.00,
                                  "budgetMonth": "2026-04"
                                }
                                """))
                .andExpect(status().isCreated());

        mockMvc.perform(put("/api/budgets/2026-04")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 5000.00,
                                  "budgetMonth": "2026-05"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Path month and request budgetMonth must match")));
    }

    @Test
    void goalEndpointsShouldCreateUpdateGetAndDeleteGoals() throws Exception {
        String token = registerAndLogin("goals@example.com");

        String goalResponse = mockMvc.perform(post("/api/goals")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Emergency Fund",
                                  "targetAmount": 100000.00,
                                  "currentAmount": 25000.00,
                                  "targetDate": "2026-12-31"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name", equalTo("Emergency Fund")))
                .andExpect(jsonPath("$.status", equalTo("ON_TRACK")))
                .andReturn()
                .getResponse()
                .getContentAsString();

        long goalId = extractLongField(goalResponse, "id");

        mockMvc.perform(get("/api/goals/" + goalId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.progressPercentage", equalTo(25.00)));

        mockMvc.perform(put("/api/goals/" + goalId)
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Emergency Fund",
                                  "targetAmount": 100000.00,
                                  "currentAmount": 100000.00,
                                  "targetDate": "2026-12-31"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("COMPLETED")))
                .andExpect(jsonPath("$.remainingAmount", equalTo(0.0)));

        mockMvc.perform(delete("/api/goals/" + goalId)
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/goals/" + goalId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void goalStatusShouldBecomeAtRiskWhenCreatedLongAgoWithLowProgress() throws Exception {
        String token = registerAndLogin("atrisk@example.com");

        String goalResponse = mockMvc.perform(post("/api/goals")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Vacation Fund",
                                  "targetAmount": 50000.00,
                                  "currentAmount": 5000.00,
                                  "targetDate": "2026-05-15"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id", notNullValue()))
                .andReturn()
                .getResponse()
                .getContentAsString();

        long goalId = extractLongField(goalResponse, "id");
        jdbcTemplate.update(
                "UPDATE goals SET created_at = ? WHERE id = ?",
                java.sql.Timestamp.valueOf(LocalDate.of(2026, 1, 1).atStartOfDay()),
                goalId
        );

        mockMvc.perform(get("/api/goals/" + goalId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("AT_RISK")));
    }

    private String registerAndLogin(String email) throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "Test User",
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
                        .header("Authorization", "Bearer " + token)
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
                        .header("Authorization", "Bearer " + token)
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

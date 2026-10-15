package com.expensetracker.expense;

import com.expensetracker.security.RateLimitService;
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

import static org.hamcrest.Matchers.equalTo;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
class ExpenseSummaryIntegrationTest {

    private MockMvc mockMvc;

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private RateLimitService rateLimitService;

    @BeforeEach
    void setUp() {
        rateLimitService.clearAll();
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
    void summaryShouldAggregateAmountsAndCountsWithinRange() throws Exception {
        String token = registerAndLogin("summary@example.com");
        long foodCategoryId = createCategory(token, "Food");

        createExpense(token, foodCategoryId, "Burger night", "2026-04-01", "300.00", "UPI");
        createExpense(token, foodCategoryId, "Lunch buffet", "2026-04-03", "800.00", "CASH");
        createExpense(token, foodCategoryId, "May dinner", "2026-05-02", "500.00", "UPI");

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("startDate", "2026-04-01")
                        .param("endDate", "2026-04-30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(1100.00)))
                .andExpect(jsonPath("$.transactionCount", equalTo(2)))
                .andExpect(jsonPath("$.startDate", equalTo("2026-04-01")))
                .andExpect(jsonPath("$.endDate", equalTo("2026-04-30")));
    }

    @Test
    void summaryShouldApplyCategoryAmountAndSearchFilters() throws Exception {
        String token = registerAndLogin("summary-filters@example.com");
        long foodCategoryId = createCategory(token, "Food");
        long travelCategoryId = createCategory(token, "Travel");

        createExpense(token, foodCategoryId, "Burger night", "2026-04-01", "300.00", "UPI");
        createExpense(token, foodCategoryId, "Lunch buffet", "2026-04-03", "800.00", "CASH");
        createExpense(token, travelCategoryId, "Train ticket", "2026-04-02", "1200.00", "CARD");

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("categoryId", String.valueOf(foodCategoryId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(1100.00)))
                .andExpect(jsonPath("$.transactionCount", equalTo(2)));

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("minAmount", "500")
                        .param("maxAmount", "1000"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(800.00)))
                .andExpect(jsonPath("$.transactionCount", equalTo(1)));

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("search", "train"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(1200.00)))
                .andExpect(jsonPath("$.transactionCount", equalTo(1)));
    }

    @Test
    void summaryShouldReturnZeroForEmptyResultSet() throws Exception {
        String token = registerAndLogin("summary-empty@example.com");
        long foodCategoryId = createCategory(token, "Food");

        createExpense(token, foodCategoryId, "Burger night", "2026-04-01", "300.00", "UPI");

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("startDate", "2020-01-01")
                        .param("endDate", "2020-12-31"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(0)))
                .andExpect(jsonPath("$.transactionCount", equalTo(0)));
    }

    @Test
    void summaryShouldOnlyIncludeTheAuthenticatedUsersExpenses() throws Exception {
        String ownerToken = registerAndLogin("summary-owner@example.com");
        String otherToken = registerAndLogin("summary-other@example.com");
        long ownerCategoryId = createCategory(ownerToken, "Owner Category");
        long otherCategoryId = createCategory(otherToken, "Other Category");

        createExpense(ownerToken, ownerCategoryId, "Owner expense", "2026-04-05", "400.00", "CARD");
        createExpense(otherToken, otherCategoryId, "Other expense", "2026-04-06", "5000.00", "CARD");

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + ownerToken)
                        .param("startDate", "2026-04-01")
                        .param("endDate", "2026-04-30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalAmount", equalTo(400.00)))
                .andExpect(jsonPath("$.transactionCount", equalTo(1)));
    }

    @Test
    void summaryShouldRejectInvalidRangesAndUnknownCategories() throws Exception {
        String token = registerAndLogin("summary-validation@example.com");

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("startDate", "2026-04-30")
                        .param("endDate", "2026-04-01"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("startDate must be before or equal to endDate")));

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("minAmount", "1000")
                        .param("maxAmount", "10"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("minAmount must be less than or equal to maxAmount")));

        mockMvc.perform(get("/api/expenses/summary")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("categoryId", "999999"))
                .andExpect(status().isNotFound());
    }

    @Test
    void summaryShouldRejectMissingToken() throws Exception {
        mockMvc.perform(get("/api/expenses/summary").contextPath("/api"))
                .andExpect(status().isForbidden());
    }

    private String registerAndLogin(String email) throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "Summary Tester",
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

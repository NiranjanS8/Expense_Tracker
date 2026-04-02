package com.expensetracker.validation;

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
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
class ValidationEdgeCaseIntegrationTest {

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
    void expenseListShouldRejectInvalidPagingSortingAndFilterRanges() throws Exception {
        String token = registerAndLogin("validation-expenses@example.com");

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("page", "-1"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Validation failed")))
                .andExpect(jsonPath("$.details[0]", containsString("Page must be zero or greater")));

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("sortBy", "unknown"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Unsupported sortBy value")));

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("startDate", "2026-04-10")
                        .param("endDate", "2026-04-01"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("startDate must be before or equal to endDate")));

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("minAmount", "500")
                        .param("maxAmount", "100"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("minAmount must be less than or equal to maxAmount")));
    }

    @Test
    void expenseCreationShouldRejectMissingCategoryWhenNoSmartRuleMatches() throws Exception {
        String token = registerAndLogin("validation-smart@example.com");

        mockMvc.perform(post("/api/expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 125.00,
                                  "expenseDate": "2026-04-02",
                                  "description": "   ",
                                  "paymentMethod": "UPI"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message",
                        equalTo("Category id is required unless a smart category rule matches the description")));
    }

    @Test
    void smartCategoryRulesShouldRejectDuplicateKeywords() throws Exception {
        String token = registerAndLogin("validation-rules@example.com");
        long categoryId = createCategory(token, "Food");

        mockMvc.perform(post("/api/smart-category-rules")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "keyword": "uber",
                                  "categoryId": %d,
                                  "active": true
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isCreated());

        mockMvc.perform(post("/api/smart-category-rules")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "keyword": " UBER ",
                                  "categoryId": %d,
                                  "active": true
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Smart category rule already exists for this keyword")));
    }

    @Test
    void budgetRequestsShouldRejectInvalidMonthAndConflictingHistoryFilters() throws Exception {
        String token = registerAndLogin("validation-budget@example.com");

        mockMvc.perform(post("/api/budgets")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 1500.00,
                                  "budgetMonth": "2026/04"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Validation failed")))
                .andExpect(jsonPath("$.details[0]", containsString("Budget month must be in yyyy-MM format")));

        mockMvc.perform(get("/api/budgets")
                        .contextPath("/api")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .param("year", "2026")
                        .param("budgetMonth", "2026-04"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message",
                        equalTo("Use either year or budgetMonth in history queries, not both")));
    }

    @Test
    void recurringStatusUpdateShouldRejectMissingActiveFlag() throws Exception {
        String token = registerAndLogin("validation-recurring@example.com");
        long categoryId = createCategory(token, "Utilities");
        String recurringResponse = mockMvc.perform(post("/api/recurring-expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": 950.00,
                                  "startDate": "2026-04-05",
                                  "description": "Monthly bill",
                                  "paymentMethod": "BANK_TRANSFER",
                                  "frequency": "MONTHLY"
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();

        long recurringExpenseId = extractLongField(recurringResponse, "id");

        mockMvc.perform(patch("/api/recurring-expenses/" + recurringExpenseId + "/status")
                        .contextPath("/api")
                        .with(csrf())
                        .header(HttpHeaders.AUTHORIZATION, bearerToken(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Validation failed")))
                .andExpect(jsonPath("$.details[0]", containsString("active is required")));
    }

    private String registerAndLogin(String email) throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "Validation Tester",
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

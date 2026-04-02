package com.expensetracker.expense;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

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
class ExpenseCategoryIntegrationTest {

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
    void categoryEndpointsShouldCreateAndListUserCategories() throws Exception {
        String token = registerAndLogin("catuser@example.com");

        mockMvc.perform(post("/api/categories")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Dining"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name", equalTo("Dining")))
                .andExpect(jsonPath("$.systemDefined", equalTo(false)));

        mockMvc.perform(get("/api/categories")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].name", equalTo("Dining")));
    }

    @Test
    void expenseCrudShouldWorkForAuthenticatedUser() throws Exception {
        String token = registerAndLogin("expenseuser@example.com");
        long categoryId = createCategory(token, "Groceries");

        String createResponse = mockMvc.perform(post("/api/expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": 450.50,
                                  "expenseDate": "2026-04-02",
                                  "description": "Weekly grocery run",
                                  "paymentMethod": "CARD"
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id", notNullValue()))
                .andExpect(jsonPath("$.categoryName", equalTo("Groceries")))
                .andReturn()
                .getResponse()
                .getContentAsString();

        long expenseId = extractLongField(createResponse, "id");

        mockMvc.perform(get("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.description", equalTo("Weekly grocery run")));

        mockMvc.perform(put("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": 499.99,
                                  "expenseDate": "2026-04-02",
                                  "description": "Updated grocery run",
                                  "paymentMethod": "CARD"
                                }
                                """.formatted(categoryId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.amount", equalTo(499.99)))
                .andExpect(jsonPath("$.description", equalTo("Updated grocery run")));

        mockMvc.perform(delete("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void expenseListShouldSupportPaginationSortingFilteringAndSearch() throws Exception {
        String token = registerAndLogin("filteruser@example.com");
        long foodCategoryId = createCategory(token, "Food");
        long travelCategoryId = createCategory(token, "Travel");

        createExpense(token, foodCategoryId, "Burger night", "2026-04-01", "300.00", "UPI");
        createExpense(token, travelCategoryId, "Train ticket", "2026-04-02", "1200.00", "CARD");
        createExpense(token, foodCategoryId, "Lunch buffet", "2026-04-03", "800.00", "CASH");

        mockMvc.perform(get("/api/expenses")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token)
                        .param("page", "0")
                        .param("size", "2")
                        .param("sortBy", "amount")
                        .param("sortDir", "desc")
                        .param("categoryId", String.valueOf(foodCategoryId))
                        .param("search", "lunch")
                        .param("minAmount", "500")
                        .param("maxAmount", "1000")
                        .param("startDate", "2026-04-01")
                        .param("endDate", "2026-04-30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content", hasSize(1)))
                .andExpect(jsonPath("$.totalElements", equalTo(1)))
                .andExpect(jsonPath("$.content[0].description", equalTo("Lunch buffet")))
                .andExpect(jsonPath("$.content[0].categoryName", equalTo("Food")));
    }

    @Test
    void smartCategoryRuleShouldAutoMapExpenseWhenCategoryIsMissing() throws Exception {
        String token = registerAndLogin("smartuser@example.com");
        long transportCategoryId = createCategory(token, "Transport");

        mockMvc.perform(post("/api/smart-category-rules")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "keyword": "uber",
                                  "categoryId": %d,
                                  "active": true
                                }
                                """.formatted(transportCategoryId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.keyword", equalTo("uber")));

        mockMvc.perform(post("/api/expenses")
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "amount": 275.00,
                                  "expenseDate": "2026-04-02",
                                  "description": "Uber ride home",
                                  "paymentMethod": "UPI"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.categoryName", equalTo("Transport")));
    }

    @Test
    void expenseEndpointsShouldEnforceUserScopedAccess() throws Exception {
        String ownerToken = registerAndLogin("owner@example.com");
        String otherToken = registerAndLogin("other@example.com");
        long ownerCategoryId = createCategory(ownerToken, "Owner Category");

        String expenseResponse = createExpense(
                ownerToken,
                ownerCategoryId,
                "Private expense",
                "2026-04-02",
                "999.00",
                "CARD"
        );
        long expenseId = extractLongField(expenseResponse, "id");

        mockMvc.perform(get("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + otherToken))
                .andExpect(status().isNotFound());

        mockMvc.perform(put("/api/expenses/" + expenseId)
                        .contextPath("/api")
                        .with(csrf())
                        .header("Authorization", "Bearer " + otherToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryId": %d,
                                  "amount": 500.00,
                                  "expenseDate": "2026-04-02",
                                  "description": "Should not update",
                                  "paymentMethod": "CARD"
                                }
                                """.formatted(ownerCategoryId)))
                .andExpect(status().isNotFound());
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

    private String createExpense(
            String token,
            long categoryId,
            String description,
            String expenseDate,
            String amount,
            String paymentMethod
    ) throws Exception {
        return mockMvc.perform(post("/api/expenses")
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
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();
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

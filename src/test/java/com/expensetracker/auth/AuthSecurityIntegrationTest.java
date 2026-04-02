package com.expensetracker.auth;

import com.expensetracker.security.RateLimitService;
import com.expensetracker.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.context.WebApplicationContext;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
class AuthSecurityIntegrationTest {

    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Autowired
    private RateLimitService rateLimitService;

    @BeforeEach
    void setUp() {
        userRepository.deleteAll();
        rateLimitService.clearAll();
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext)
                .apply(SecurityMockMvcConfigurers.springSecurity())
                .build();
    }

    @Test
    void registerShouldCreateUserAndReturnToken() throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "Test User",
                                  "email": "test@example.com",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.accessToken", notNullValue()))
                .andExpect(jsonPath("$.tokenType", equalTo("Bearer")))
                .andExpect(jsonPath("$.user.email", equalTo("test@example.com")))
                .andExpect(jsonPath("$.user.fullName", equalTo("Test User")));
    }

    @Test
    void registerShouldRejectDuplicateEmail() throws Exception {
        String requestBody = """
                {
                  "fullName": "Test User",
                  "email": "duplicate@example.com",
                  "password": "Password@123"
                }
                """;

        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestBody))
                .andExpect(status().isCreated());

        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestBody))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Email is already registered")));
    }

    @Test
    void loginShouldReturnTokenForValidCredentials() throws Exception {
        registerUser("login@example.com");

        mockMvc.perform(post("/api/auth/login")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "login@example.com",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken", notNullValue()))
                .andExpect(jsonPath("$.user.email", equalTo("login@example.com")));
    }

    @Test
    void loginShouldRejectInvalidCredentials() throws Exception {
        registerUser("wrongpass@example.com");

        mockMvc.perform(post("/api/auth/login")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "wrongpass@example.com",
                                  "password": "WrongPassword@123"
                                }
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message", equalTo("Invalid email or password")));
    }

    @Test
    void protectedEndpointShouldRejectMissingToken() throws Exception {
        mockMvc.perform(get("/api/users/me").contextPath("/api"))
                .andExpect(status().isForbidden());
    }

    @Test
    void protectedEndpointShouldAllowValidToken() throws Exception {
        registerUser("secure@example.com");

        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "secure@example.com",
                                  "password": "Password@123"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        String token = extractAccessToken(loginResponse);

        mockMvc.perform(get("/api/users/me")
                        .contextPath("/api")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email", equalTo("secure@example.com")))
                .andExpect(jsonPath("$.role", equalTo("USER")));
    }

    @Test
    void registerShouldValidateRequestBody() throws Exception {
        mockMvc.perform(post("/api/auth/register")
                        .contextPath("/api")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName": "",
                                  "email": "bad-email",
                                  "password": "123"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", equalTo("Validation failed")))
                .andExpect(jsonPath("$.details", hasSize(3)));
    }

    @Test
    void loginShouldRateLimitByClientIp() throws Exception {
        registerUser("ratelimit-login@example.com");

        for (int attempt = 0; attempt < 5; attempt++) {
            mockMvc.perform(post("/api/auth/login")
                            .contextPath("/api")
                            .with(csrf())
                            .with(request -> {
                                request.setRemoteAddr("10.0.0.1");
                                return request;
                            })
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {
                                      "email": "ratelimit-login@example.com",
                                      "password": "WrongPassword@123"
                                    }
                                    """))
                    .andExpect(status().isUnauthorized());
        }

        mockMvc.perform(post("/api/auth/login")
                        .contextPath("/api")
                        .with(csrf())
                        .with(request -> {
                            request.setRemoteAddr("10.0.0.1");
                            return request;
                        })
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "email": "ratelimit-login@example.com",
                                  "password": "WrongPassword@123"
                                }
                                """))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.message", equalTo("Too many login attempts. Please try again later.")));
    }

    private void registerUser(String email) throws Exception {
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
    }

    private String extractAccessToken(String loginResponse) {
        String marker = "\"accessToken\":\"";
        int start = loginResponse.indexOf(marker);
        int tokenStart = start + marker.length();
        int tokenEnd = loginResponse.indexOf('"', tokenStart);
        return loginResponse.substring(tokenStart, tokenEnd);
    }
}

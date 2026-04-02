package com.expensetracker.recurring.controller;

import com.expensetracker.recurring.dto.RecurringExpenseRequest;
import com.expensetracker.recurring.dto.RecurringExpenseResponse;
import com.expensetracker.recurring.dto.RecurringExpenseStatusRequest;
import com.expensetracker.recurring.dto.RecurringGenerationResponse;
import com.expensetracker.recurring.service.RecurringExpenseService;
import com.expensetracker.security.RateLimitService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/recurring-expenses")
@RequiredArgsConstructor
public class RecurringExpenseController {

    private final RecurringExpenseService recurringExpenseService;
    private final RateLimitService rateLimitService;

    @GetMapping
    public List<RecurringExpenseResponse> getRecurringExpenses(@AuthenticationPrincipal User user) {
        return recurringExpenseService.getRecurringExpenses(user);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public RecurringExpenseResponse createRecurringExpense(
            @Valid @RequestBody RecurringExpenseRequest request,
            @AuthenticationPrincipal User user
    ) {
        return recurringExpenseService.createRecurringExpense(request, user);
    }

    @PutMapping("/{recurringExpenseId}")
    public RecurringExpenseResponse updateRecurringExpense(
            @PathVariable Long recurringExpenseId,
            @Valid @RequestBody RecurringExpenseRequest request,
            @AuthenticationPrincipal User user
    ) {
        return recurringExpenseService.updateRecurringExpense(recurringExpenseId, request, user);
    }

    @PatchMapping("/{recurringExpenseId}/status")
    public RecurringExpenseResponse updateRecurringExpenseStatus(
            @PathVariable Long recurringExpenseId,
            @Valid @RequestBody RecurringExpenseStatusRequest request,
            @AuthenticationPrincipal User user
    ) {
        return recurringExpenseService.updateRecurringExpenseStatus(recurringExpenseId, request.active(), user);
    }

    @PostMapping("/generate")
    public RecurringGenerationResponse generateRecurringExpenses(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate runDate
    ) {
        rateLimitService.checkRecurringGenerationRateLimit(user);
        return recurringExpenseService.generateDueRecurringExpensesForUser(
                runDate == null ? LocalDate.now() : runDate,
                user
        );
    }
}

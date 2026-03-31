package com.expensetracker.expense.controller;

import com.expensetracker.common.dto.PagedResponse;
import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.service.ExpenseService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;

@RestController
@Validated
@RequestMapping("/expenses")
@RequiredArgsConstructor
public class ExpenseController {

    private final ExpenseService expenseService;

    @GetMapping
    public PagedResponse<ExpenseResponse> getExpenses(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") @Min(value = 0, message = "Page must be zero or greater") int page,
            @RequestParam(defaultValue = "10") @Min(value = 1, message = "Size must be at least 1")
            @Max(value = 100, message = "Size must be at most 100") int size
    ) {
        return expenseService.getExpenses(user, page, size);
    }

    @GetMapping("/{expenseId}")
    public ExpenseResponse getExpenseById(
            @PathVariable Long expenseId,
            @AuthenticationPrincipal User user
    ) {
        return expenseService.getExpenseById(expenseId, user);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ExpenseResponse createExpense(
            @Valid @RequestBody ExpenseRequest request,
            @AuthenticationPrincipal User user
    ) {
        return expenseService.createExpense(request, user);
    }

    @PutMapping("/{expenseId}")
    public ExpenseResponse updateExpense(
            @PathVariable Long expenseId,
            @Valid @RequestBody ExpenseRequest request,
            @AuthenticationPrincipal User user
    ) {
        return expenseService.updateExpense(expenseId, request, user);
    }

    @DeleteMapping("/{expenseId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteExpense(
            @PathVariable Long expenseId,
            @AuthenticationPrincipal User user
    ) {
        expenseService.deleteExpense(expenseId, user);
    }
}

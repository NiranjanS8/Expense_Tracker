package com.expensetracker.expense.controller;

import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.service.ExpenseService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import java.util.List;
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
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/expenses")
@RequiredArgsConstructor
public class ExpenseController {

    private final ExpenseService expenseService;

    @GetMapping
    public List<ExpenseResponse> getExpenses(@AuthenticationPrincipal User user) {
        return expenseService.getExpenses(user);
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

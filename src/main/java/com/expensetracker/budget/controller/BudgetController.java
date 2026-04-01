package com.expensetracker.budget.controller;

import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.service.BudgetService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import java.time.YearMonth;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
@RequestMapping("/budgets")
@RequiredArgsConstructor
public class BudgetController {

    private final BudgetService budgetService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public BudgetSummaryResponse createBudget(
            @Valid @RequestBody BudgetRequest request,
            @AuthenticationPrincipal User user
    ) {
        return budgetService.createBudget(request, user);
    }

    @PutMapping("/{budgetMonth}")
    public BudgetSummaryResponse updateBudget(
            @PathVariable @DateTimeFormat(pattern = "yyyy-MM") YearMonth budgetMonth,
            @Valid @RequestBody BudgetRequest request,
            @AuthenticationPrincipal User user
    ) {
        return budgetService.updateBudget(budgetMonth, request, user);
    }

    @GetMapping("/{budgetMonth}")
    public BudgetSummaryResponse getBudgetByMonth(
            @PathVariable @DateTimeFormat(pattern = "yyyy-MM") YearMonth budgetMonth,
            @AuthenticationPrincipal User user
    ) {
        return budgetService.getBudgetByMonth(budgetMonth, user);
    }

    @GetMapping("/current")
    public BudgetSummaryResponse getCurrentMonthBudget(@AuthenticationPrincipal User user) {
        return budgetService.getCurrentMonthBudget(user);
    }
}

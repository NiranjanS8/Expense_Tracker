package com.expensetracker.budget.controller;

import com.expensetracker.budget.dto.BudgetQueryParams;
import com.expensetracker.budget.dto.BudgetRequest;
import com.expensetracker.budget.dto.BudgetSummaryResponse;
import com.expensetracker.budget.service.BudgetCommandService;
import com.expensetracker.budget.service.BudgetQueryService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
@RequestMapping("/budgets")
@RequiredArgsConstructor
public class BudgetController {

    private final BudgetCommandService budgetCommandService;
    private final BudgetQueryService budgetQueryService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public BudgetSummaryResponse createBudget(
            @Valid @RequestBody BudgetRequest request,
            @AuthenticationPrincipal User user
    ) {
        return budgetCommandService.createBudget(request, user);
    }

    @PutMapping("/{budgetMonth}")
    public BudgetSummaryResponse updateBudget(
            @PathVariable String budgetMonth,
            @Valid @RequestBody BudgetRequest request,
            @AuthenticationPrincipal User user
    ) {
        return budgetCommandService.updateBudget(budgetMonth, request, user);
    }

    @GetMapping("/{budgetMonth}")
    public BudgetSummaryResponse getBudgetByMonth(
            @PathVariable String budgetMonth,
            @AuthenticationPrincipal User user
    ) {
        return budgetQueryService.getBudgetByMonth(budgetMonth, user);
    }

    @GetMapping("/current")
    public BudgetSummaryResponse getCurrentMonthBudget(@AuthenticationPrincipal User user) {
        return budgetQueryService.getCurrentMonthBudget(user);
    }

    @GetMapping
    public List<BudgetSummaryResponse> getBudgetHistory(
            @AuthenticationPrincipal User user,
            @RequestParam(required = false) String budgetMonth,
            @RequestParam(required = false) @Min(value = 2000, message = "year must be 2000 or greater")
            @Max(value = 2100, message = "year must be 2100 or less") Integer year
    ) {
        return budgetQueryService.getBudgetHistory(new BudgetQueryParams(budgetMonth, year), user);
    }
}

package com.expensetracker.smartcategory.controller;

import com.expensetracker.smartcategory.dto.SmartCategoryRuleRequest;
import com.expensetracker.smartcategory.dto.SmartCategoryRuleResponse;
import com.expensetracker.smartcategory.service.SmartCategoryService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
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

import java.util.List;

@RestController
@RequestMapping("/smart-category-rules")
@RequiredArgsConstructor
public class SmartCategoryRuleController {

    private final SmartCategoryService smartCategoryService;

    @GetMapping
    public List<SmartCategoryRuleResponse> getRules(@AuthenticationPrincipal User user) {
        return smartCategoryService.getRules(user);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SmartCategoryRuleResponse createRule(
            @Valid @RequestBody SmartCategoryRuleRequest request,
            @AuthenticationPrincipal User user
    ) {
        return smartCategoryService.createRule(request, user);
    }

    @PutMapping("/{ruleId}")
    public SmartCategoryRuleResponse updateRule(
            @PathVariable Long ruleId,
            @Valid @RequestBody SmartCategoryRuleRequest request,
            @AuthenticationPrincipal User user
    ) {
        return smartCategoryService.updateRule(ruleId, request, user);
    }

    @DeleteMapping("/{ruleId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteRule(@PathVariable Long ruleId, @AuthenticationPrincipal User user) {
        smartCategoryService.deleteRule(ruleId, user);
    }
}

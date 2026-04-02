package com.expensetracker.goals.controller;

import com.expensetracker.goals.dto.GoalRequest;
import com.expensetracker.goals.dto.GoalResponse;
import com.expensetracker.goals.service.GoalService;
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
@RequestMapping("/goals")
@RequiredArgsConstructor
public class GoalController {

    private final GoalService goalService;

    @GetMapping
    public List<GoalResponse> getGoals(@AuthenticationPrincipal User user) {
        return goalService.getGoals(user);
    }

    @GetMapping("/{goalId}")
    public GoalResponse getGoal(@PathVariable Long goalId, @AuthenticationPrincipal User user) {
        return goalService.getGoal(goalId, user);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public GoalResponse createGoal(
            @Valid @RequestBody GoalRequest request,
            @AuthenticationPrincipal User user
    ) {
        return goalService.createGoal(request, user);
    }

    @PutMapping("/{goalId}")
    public GoalResponse updateGoal(
            @PathVariable Long goalId,
            @Valid @RequestBody GoalRequest request,
            @AuthenticationPrincipal User user
    ) {
        return goalService.updateGoal(goalId, request, user);
    }

    @DeleteMapping("/{goalId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteGoal(@PathVariable Long goalId, @AuthenticationPrincipal User user) {
        goalService.deleteGoal(goalId, user);
    }
}

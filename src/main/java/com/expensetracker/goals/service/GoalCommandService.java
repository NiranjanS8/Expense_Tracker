package com.expensetracker.goals.service;

import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.goals.dto.GoalRequest;
import com.expensetracker.goals.dto.GoalResponse;
import com.expensetracker.goals.entity.Goal;
import com.expensetracker.goals.repository.GoalRepository;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class GoalCommandService {

    private final GoalRepository goalRepository;
    private final GoalQueryService goalQueryService;

    @Transactional
    public GoalResponse createGoal(GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = new Goal();
        goal.setUser(user);
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        return goalQueryService.toResponse(goalRepository.save(goal));
    }

    @Transactional
    public GoalResponse updateGoal(Long goalId, GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = goalQueryService.findGoal(goalId, user.getId());
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        return goalQueryService.toResponse(goal);
    }

    @Transactional
    public void deleteGoal(Long goalId, User user) {
        goalRepository.delete(goalQueryService.findGoal(goalId, user.getId()));
    }

    private void validateGoalAmounts(BigDecimal currentAmount, BigDecimal targetAmount) {
        if (currentAmount.compareTo(targetAmount) > 0) {
            throw new BadRequestException("Current amount cannot be greater than target amount");
        }
    }
}

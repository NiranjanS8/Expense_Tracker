package com.expensetracker.goals.service;

import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.goals.dto.GoalRequest;
import com.expensetracker.goals.dto.GoalResponse;
import com.expensetracker.goals.entity.Goal;
import com.expensetracker.goals.event.GoalChangeType;
import com.expensetracker.goals.event.GoalChangedEvent;
import com.expensetracker.goals.repository.GoalRepository;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class GoalCommandService {

    private final GoalRepository goalRepository;
    private final GoalQueryService goalQueryService;
    private final ApplicationEventPublisher applicationEventPublisher;

    @Transactional
    public GoalResponse createGoal(GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = new Goal();
        goal.setUser(user);
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        Goal savedGoal = goalRepository.save(goal);
        publishGoalChanged(savedGoal, GoalChangeType.CREATED);
        return goalQueryService.toResponse(savedGoal);
    }

    @Transactional
    public GoalResponse updateGoal(Long goalId, GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = goalQueryService.findGoal(goalId, user.getId());
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        publishGoalChanged(goal, GoalChangeType.UPDATED);
        return goalQueryService.toResponse(goal);
    }

    @Transactional
    public void deleteGoal(Long goalId, User user) {
        Goal goal = goalQueryService.findGoal(goalId, user.getId());
        goalRepository.delete(goal);
        publishGoalChanged(goal, GoalChangeType.DELETED);
    }

    private void validateGoalAmounts(BigDecimal currentAmount, BigDecimal targetAmount) {
        if (currentAmount.compareTo(targetAmount) > 0) {
            throw new BadRequestException("Current amount cannot be greater than target amount");
        }
    }

    private void publishGoalChanged(Goal goal, GoalChangeType changeType) {
        applicationEventPublisher.publishEvent(new GoalChangedEvent(
                goal.getId(),
                goal.getUser().getId(),
                goal.getName(),
                goal.getTargetAmount(),
                goal.getCurrentAmount(),
                goal.getTargetDate(),
                changeType
        ));
    }
}

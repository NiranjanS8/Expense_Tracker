package com.expensetracker.goals.service;

import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.goals.dto.GoalRequest;
import com.expensetracker.goals.dto.GoalResponse;
import com.expensetracker.goals.dto.GoalStatus;
import com.expensetracker.goals.entity.Goal;
import com.expensetracker.goals.repository.GoalRepository;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Service
@RequiredArgsConstructor
public class GoalService {

    private final GoalRepository goalRepository;

    @Transactional(readOnly = true)
    public List<GoalResponse> getGoals(User user) {
        return goalRepository.findAllByUserIdOrderByTargetDateAscCreatedAtDesc(user.getId())
                .stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional(readOnly = true)
    public GoalResponse getGoal(Long goalId, User user) {
        return toResponse(findGoal(goalId, user.getId()));
    }

    @Transactional
    public GoalResponse createGoal(GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = new Goal();
        goal.setUser(user);
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        return toResponse(goalRepository.save(goal));
    }

    @Transactional
    public GoalResponse updateGoal(Long goalId, GoalRequest request, User user) {
        validateGoalAmounts(request.currentAmount(), request.targetAmount());

        Goal goal = findGoal(goalId, user.getId());
        goal.setName(request.name().trim());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());

        return toResponse(goal);
    }

    @Transactional
    public void deleteGoal(Long goalId, User user) {
        goalRepository.delete(findGoal(goalId, user.getId()));
    }

    private Goal findGoal(Long goalId, Long userId) {
        return goalRepository.findByIdAndUserId(goalId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Goal not found"));
    }

    private GoalResponse toResponse(Goal goal) {
        BigDecimal remainingAmount = goal.getTargetAmount().subtract(goal.getCurrentAmount()).max(BigDecimal.ZERO);
        BigDecimal progressPercentage = calculateProgress(goal.getCurrentAmount(), goal.getTargetAmount());
        BigDecimal requiredMonthlyContribution = calculateRequiredMonthlyContribution(remainingAmount, goal.getTargetDate());
        GoalStatus status = determineStatus(goal, progressPercentage);

        return new GoalResponse(
                goal.getId(),
                goal.getName(),
                goal.getTargetAmount(),
                goal.getCurrentAmount(),
                remainingAmount,
                progressPercentage,
                requiredMonthlyContribution,
                goal.getTargetDate(),
                status
        );
    }

    private BigDecimal calculateProgress(BigDecimal currentAmount, BigDecimal targetAmount) {
        if (targetAmount.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }

        return currentAmount.multiply(BigDecimal.valueOf(100))
                .divide(targetAmount, 2, RoundingMode.HALF_UP);
    }

    private BigDecimal calculateRequiredMonthlyContribution(BigDecimal remainingAmount, LocalDate targetDate) {
        if (remainingAmount.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }

        long monthsRemaining = Math.max(1, ChronoUnit.MONTHS.between(
                LocalDate.now().withDayOfMonth(1),
                targetDate.withDayOfMonth(1)
        ) + 1);

        return remainingAmount.divide(BigDecimal.valueOf(monthsRemaining), 2, RoundingMode.HALF_UP);
    }

    private GoalStatus determineStatus(Goal goal, BigDecimal progressPercentage) {
        if (goal.getCurrentAmount().compareTo(goal.getTargetAmount()) >= 0) {
            return GoalStatus.COMPLETED;
        }

        if (goal.getTargetDate().isBefore(LocalDate.now())) {
            return GoalStatus.OVERDUE;
        }

        LocalDate today = LocalDate.now();
        LocalDate goalCreatedDate = goal.getCreatedAt() == null
                ? today
                : goal.getCreatedAt().atZone(java.time.ZoneOffset.UTC).toLocalDate();
        long totalGoalDays = Math.max(1, ChronoUnit.DAYS.between(goalCreatedDate, goal.getTargetDate()));
        long elapsedGoalDays = Math.max(0, ChronoUnit.DAYS.between(goalCreatedDate, today));

        BigDecimal elapsedRatioPercentage = BigDecimal.valueOf(elapsedGoalDays)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(totalGoalDays), 2, RoundingMode.HALF_UP);

        if (progressPercentage.compareTo(elapsedRatioPercentage.subtract(BigDecimal.valueOf(15))) < 0) {
            return GoalStatus.AT_RISK;
        }

        return GoalStatus.ON_TRACK;
    }

    private void validateGoalAmounts(BigDecimal currentAmount, BigDecimal targetAmount) {
        if (currentAmount.compareTo(targetAmount) > 0) {
            throw new BadRequestException("Current amount cannot be greater than target amount");
        }
    }
}

package com.expensetracker.goals.service;

import com.expensetracker.goals.dto.GoalRequest;
import com.expensetracker.goals.entity.Goal;
import com.expensetracker.goals.event.GoalChangeType;
import com.expensetracker.goals.event.GoalChangedEvent;
import com.expensetracker.goals.repository.GoalRepository;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GoalCommandServiceTest {

    @Mock
    private GoalRepository goalRepository;

    @Mock
    private GoalQueryService goalQueryService;

    @Mock
    private ApplicationEventPublisher applicationEventPublisher;

    private GoalCommandService goalCommandService;

    @BeforeEach
    void setUp() {
        goalCommandService = new GoalCommandService(
                goalRepository,
                goalQueryService,
                applicationEventPublisher
        );
    }

    @Test
    void createGoalShouldPublishCreatedEvent() {
        User user = createUser(1L);
        GoalRequest request = new GoalRequest(
                "Emergency Fund",
                new BigDecimal("100000.00"),
                new BigDecimal("25000.00"),
                LocalDate.of(2026, 12, 31)
        );
        Goal savedGoal = createGoal(10L, user, request);

        when(goalRepository.save(any(Goal.class))).thenReturn(savedGoal);
        when(goalQueryService.toResponse(savedGoal)).thenReturn(null);

        goalCommandService.createGoal(request, user);

        ArgumentCaptor<GoalChangedEvent> eventCaptor = ArgumentCaptor.forClass(GoalChangedEvent.class);
        verify(applicationEventPublisher).publishEvent(eventCaptor.capture());
        GoalChangedEvent event = eventCaptor.getValue();
        assertEquals(savedGoal.getId(), event.goalId());
        assertEquals(user.getId(), event.userId());
        assertEquals("Emergency Fund", event.name());
        assertEquals(GoalChangeType.CREATED, event.changeType());
    }

    @Test
    void updateAndDeleteGoalShouldPublishUpdatedAndDeletedEvents() {
        User user = createUser(2L);
        Goal goal = createGoal(11L, user, new GoalRequest(
                "Vacation Fund",
                new BigDecimal("50000.00"),
                new BigDecimal("5000.00"),
                LocalDate.of(2026, 10, 31)
        ));
        GoalRequest updateRequest = new GoalRequest(
                "Vacation Fund",
                new BigDecimal("50000.00"),
                new BigDecimal("15000.00"),
                LocalDate.of(2026, 10, 31)
        );

        when(goalQueryService.findGoal(goal.getId(), user.getId())).thenReturn(goal);
        when(goalQueryService.toResponse(goal)).thenReturn(null);

        goalCommandService.updateGoal(goal.getId(), updateRequest, user);
        goalCommandService.deleteGoal(goal.getId(), user);

        ArgumentCaptor<GoalChangedEvent> eventCaptor = ArgumentCaptor.forClass(GoalChangedEvent.class);
        verify(applicationEventPublisher, org.mockito.Mockito.times(2)).publishEvent(eventCaptor.capture());
        assertEquals(GoalChangeType.UPDATED, eventCaptor.getAllValues().get(0).changeType());
        assertEquals(GoalChangeType.DELETED, eventCaptor.getAllValues().get(1).changeType());
        assertEquals(new BigDecimal("15000.00"), eventCaptor.getAllValues().get(1).currentAmount());
        verify(goalRepository).delete(goal);
    }

    private User createUser(Long id) {
        User user = new User();
        user.setId(id);
        user.setFullName("Goal Event Tester");
        user.setEmail("goal-event@test.com");
        user.setPassword("encoded");
        user.setRole(Role.USER);
        return user;
    }

    private Goal createGoal(Long id, User user, GoalRequest request) {
        Goal goal = new Goal();
        goal.setId(id);
        goal.setUser(user);
        goal.setName(request.name());
        goal.setTargetAmount(request.targetAmount());
        goal.setCurrentAmount(request.currentAmount());
        goal.setTargetDate(request.targetDate());
        return goal;
    }
}

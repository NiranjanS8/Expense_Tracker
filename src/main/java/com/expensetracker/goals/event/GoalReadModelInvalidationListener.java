package com.expensetracker.goals.event;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Slf4j
@Component
public class GoalReadModelInvalidationListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleGoalChanged(GoalChangedEvent event) {
        log.info(
                "Goal {} {} for user {}. Dependent progress views targeting {} should refresh.",
                event.goalId(),
                event.changeType().name().toLowerCase(),
                event.userId(),
                event.targetDate()
        );
    }
}

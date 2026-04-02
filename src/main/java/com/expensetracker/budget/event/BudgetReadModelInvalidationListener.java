package com.expensetracker.budget.event;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Slf4j
@Component
public class BudgetReadModelInvalidationListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleBudgetChanged(BudgetChangedEvent event) {
        log.info(
                "Budget {} {} for user {}. Dependent read models for {} should refresh.",
                event.budgetId(),
                event.changeType().name().toLowerCase(),
                event.userId(),
                event.budgetMonth()
        );
    }
}

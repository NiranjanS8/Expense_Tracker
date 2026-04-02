package com.expensetracker.expense.event;

import java.time.YearMonth;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Slf4j
@Component
public class ExpenseReadModelInvalidationListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleExpenseChanged(ExpenseChangedEvent event) {
        YearMonth affectedMonth = YearMonth.from(event.expenseDate());
        log.info(
                "Expense {} {} for user {}. Dependent read models for {} should refresh.",
                event.expenseId(),
                event.changeType().name().toLowerCase(),
                event.userId(),
                affectedMonth
        );
    }
}

package com.expensetracker.expense.repository;

import com.expensetracker.expense.entity.Expense;
import org.springframework.data.jpa.domain.Specification;

public interface ExpenseSummaryRepository {

    ExpenseAggregate summarize(Specification<Expense> specification);
}

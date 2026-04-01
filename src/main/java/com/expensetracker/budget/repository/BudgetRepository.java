package com.expensetracker.budget.repository;

import com.expensetracker.budget.entity.Budget;
import java.time.YearMonth;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BudgetRepository extends JpaRepository<Budget, Long> {

    Optional<Budget> findByUserIdAndBudgetMonth(Long userId, YearMonth budgetMonth);

    boolean existsByUserIdAndBudgetMonth(Long userId, YearMonth budgetMonth);

    List<Budget> findAllByUserIdOrderByBudgetMonthDesc(Long userId);

    List<Budget> findAllByUserIdAndBudgetMonthBetweenOrderByBudgetMonthDesc(
            Long userId,
            YearMonth startMonth,
            YearMonth endMonth
    );
}

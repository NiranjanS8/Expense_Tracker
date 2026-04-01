package com.expensetracker.recurring.repository;

import com.expensetracker.recurring.entity.RecurringExpense;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface RecurringExpenseRepository extends JpaRepository<RecurringExpense, Long> {

    List<RecurringExpense> findAllByUserIdOrderByCreatedAtDesc(Long userId);

    Optional<RecurringExpense> findByIdAndUserId(Long id, Long userId);

    List<RecurringExpense> findAllByActiveTrueAndNextExecutionDateLessThanEqual(LocalDate date);
}

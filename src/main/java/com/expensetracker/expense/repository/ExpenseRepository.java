package com.expensetracker.expense.repository;

import com.expensetracker.expense.entity.Expense;
import com.expensetracker.dashboard.dto.CategorySpendingResponse;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ExpenseRepository extends JpaRepository<Expense, Long>, JpaSpecificationExecutor<Expense> {

    Page<Expense> findAllByUserId(Long userId, Pageable pageable);

    Optional<Expense> findByIdAndUserId(Long id, Long userId);

    boolean existsByRecurringExpenseIdAndExpenseDate(Long recurringExpenseId, LocalDate expenseDate);

    long countByUserId(Long userId);

    long countByUserIdAndExpenseDateBetween(Long userId, LocalDate startDate, LocalDate endDate);

    @Query("""
            select coalesce(sum(e.amount), 0)
            from Expense e
            where e.user.id = :userId
              and e.expenseDate between :startDate and :endDate
            """)
    BigDecimal sumAmountByUserIdAndExpenseDateBetween(
            @Param("userId") Long userId,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate
    );

    @Query("""
            select e
            from Expense e
            where e.user.id = :userId
            order by e.expenseDate desc, e.id desc
            """)
    List<Expense> findTopByUserIdOrderByExpenseDateDescIdDesc(@Param("userId") Long userId, Pageable pageable);

    @Query("""
            select e
            from Expense e
            where e.user.id = :userId
              and e.expenseDate between :startDate and :endDate
            order by e.amount desc, e.id desc
            """)
    List<Expense> findTopByUserIdAndExpenseDateBetweenOrderByAmountDescIdDesc(
            @Param("userId") Long userId,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate,
            Pageable pageable
    );

    default List<Expense> findTopByUserIdOrderByExpenseDateDescIdDesc(Long userId, int limit) {
        return findTopByUserIdOrderByExpenseDateDescIdDesc(userId, Pageable.ofSize(limit));
    }

    @Query("""
            select new com.expensetracker.dashboard.dto.CategorySpendingResponse(
                e.category.id,
                e.category.name,
                coalesce(sum(e.amount), 0)
            )
            from Expense e
            where e.user.id = :userId
              and e.expenseDate between :startDate and :endDate
            group by e.category.id, e.category.name
            order by sum(e.amount) desc, e.category.name asc
            """)
    List<CategorySpendingResponse> findCategorySpendingByUserIdAndExpenseDateBetween(
            @Param("userId") Long userId,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate
    );

    @Query("""
            select year(e.expenseDate), month(e.expenseDate), coalesce(sum(e.amount), 0)
            from Expense e
            where e.user.id = :userId
              and e.expenseDate >= :startDate
            group by year(e.expenseDate), month(e.expenseDate)
            order by year(e.expenseDate), month(e.expenseDate)
            """)
    List<Object[]> findMonthlyTrendByUserIdFromDate(
            @Param("userId") Long userId,
            @Param("startDate") LocalDate startDate
    );
}

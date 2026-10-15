package com.expensetracker.expense.repository;

import com.expensetracker.expense.entity.Expense;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Tuple;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import java.math.BigDecimal;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Repository;

@Repository
public class ExpenseSummaryRepositoryImpl implements ExpenseSummaryRepository {

    private final EntityManager entityManager;

    public ExpenseSummaryRepositoryImpl(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    @Override
    public ExpenseAggregate summarize(Specification<Expense> specification) {
        CriteriaBuilder criteriaBuilder = entityManager.getCriteriaBuilder();
        CriteriaQuery<Tuple> query = criteriaBuilder.createTupleQuery();
        Root<Expense> root = query.from(Expense.class);

        Predicate predicate = specification.toPredicate(root, query, criteriaBuilder);
        query.where(predicate);
        query.multiselect(
                criteriaBuilder.coalesce(criteriaBuilder.sum(root.<BigDecimal>get("amount")), BigDecimal.ZERO),
                criteriaBuilder.count(root)
        );

        Tuple result = entityManager.createQuery(query).getSingleResult();
        BigDecimal totalAmount = result.get(0, BigDecimal.class);
        return new ExpenseAggregate(totalAmount == null ? BigDecimal.ZERO : totalAmount, result.get(1, Long.class));
    }
}

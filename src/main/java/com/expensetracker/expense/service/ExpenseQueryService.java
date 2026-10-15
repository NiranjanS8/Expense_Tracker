package com.expensetracker.expense.service;

import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.dto.PagedResponse;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.dto.ExpenseSummaryParams;
import com.expensetracker.expense.dto.ExpenseSummaryResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseAggregate;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.expense.repository.ExpenseSpecifications;
import com.expensetracker.user.entity.User;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ExpenseQueryService {

    private static final int MAX_EXPORT_ROWS = 5000;
    private static final Map<String, String> SORT_FIELDS = Map.of(
            "expenseDate", "expenseDate",
            "amount", "amount",
            "createdAt", "createdAt"
    );
    private static final String SORT_DIRECTION_ASC = "asc";
    private static final String SORT_DIRECTION_DESC = "desc";

    private final ExpenseRepository expenseRepository;
    private final CategoryService categoryService;

    @Transactional(readOnly = true)
    public PagedResponse<ExpenseResponse> getExpenses(User user, ExpenseQueryParams queryParams) {
        validateQueryParams(queryParams);
        if (queryParams.categoryId() != null) {
            categoryService.getAccessibleCategory(queryParams.categoryId(), user.getId());
        }

        Pageable pageable = PageRequest.of(
                queryParams.page(),
                queryParams.size(),
                buildSort(queryParams.sortBy(), queryParams.sortDir())
        );

        Specification<Expense> specification = buildSpecification(user.getId(), queryParams);

        return PagedResponse.from(expenseRepository.findAll(specification, pageable)
                .map(ExpenseResponse::from));
    }

    @Transactional(readOnly = true)
    public List<ExpenseResponse> getExpensesForExport(User user, ExpenseQueryParams queryParams) {
        validateQueryParams(queryParams);
        if (queryParams.categoryId() != null) {
            categoryService.getAccessibleCategory(queryParams.categoryId(), user.getId());
        }

        Sort sort = buildSort(queryParams.sortBy(), queryParams.sortDir());
        Specification<Expense> specification = buildSpecification(user.getId(), queryParams);
        long matchingExpenseCount = expenseRepository.count(specification);
        if (matchingExpenseCount > MAX_EXPORT_ROWS) {
            throw new BadRequestException("Export is limited to 5000 expenses. Narrow the filters and try again.");
        }

        return expenseRepository.findAll(specification, PageRequest.of(0, MAX_EXPORT_ROWS, sort))
                .stream()
                .map(ExpenseResponse::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public ExpenseResponse getExpenseById(Long expenseId, User user) {
        return ExpenseResponse.from(findUserExpense(expenseId, user.getId()));
    }

    @Transactional(readOnly = true)
    public ExpenseSummaryResponse getSummary(User user, ExpenseSummaryParams summaryParams) {
        validateRanges(
                summaryParams.startDate(),
                summaryParams.endDate(),
                summaryParams.minAmount(),
                summaryParams.maxAmount()
        );
        if (summaryParams.categoryId() != null) {
            categoryService.getAccessibleCategory(summaryParams.categoryId(), user.getId());
        }

        Specification<Expense> specification = buildSpecification(user.getId(), summaryParams);
        ExpenseAggregate aggregate = expenseRepository.summarize(specification);

        return new ExpenseSummaryResponse(
                aggregate.totalAmount(),
                aggregate.transactionCount(),
                summaryParams.startDate(),
                summaryParams.endDate()
        );
    }

    @Transactional(readOnly = true)
    public Expense findUserExpense(Long expenseId, Long userId) {
        return expenseRepository.findByIdAndUserId(expenseId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Expense not found"));
    }

    private Specification<Expense> buildSpecification(Long userId, ExpenseQueryParams queryParams) {
        return buildSpecification(
                userId,
                queryParams.categoryId(),
                queryParams.startDate(),
                queryParams.endDate(),
                queryParams.minAmount(),
                queryParams.maxAmount(),
                queryParams.search()
        );
    }

    private Specification<Expense> buildSpecification(Long userId, ExpenseSummaryParams summaryParams) {
        return buildSpecification(
                userId,
                summaryParams.categoryId(),
                summaryParams.startDate(),
                summaryParams.endDate(),
                summaryParams.minAmount(),
                summaryParams.maxAmount(),
                summaryParams.search()
        );
    }

    private Specification<Expense> buildSpecification(
            Long userId,
            Long categoryId,
            LocalDate startDate,
            LocalDate endDate,
            BigDecimal minAmount,
            BigDecimal maxAmount,
            String search
    ) {
        Specification<Expense> specification = Specification.where(ExpenseSpecifications.hasUserId(userId));

        if (categoryId != null) {
            specification = specification.and(ExpenseSpecifications.hasCategoryId(categoryId));
        }
        if (startDate != null) {
            specification = specification.and(ExpenseSpecifications.expenseDateGreaterThanOrEqualTo(startDate));
        }
        if (endDate != null) {
            specification = specification.and(ExpenseSpecifications.expenseDateLessThanOrEqualTo(endDate));
        }
        if (minAmount != null) {
            specification = specification.and(ExpenseSpecifications.amountGreaterThanOrEqualTo(minAmount));
        }
        if (maxAmount != null) {
            specification = specification.and(ExpenseSpecifications.amountLessThanOrEqualTo(maxAmount));
        }
        if (hasText(search)) {
            specification = specification.and(ExpenseSpecifications.matchesSearchTerm(search.trim()));
        }

        return specification;
    }

    private Sort buildSort(String sortBy, String sortDir) {
        String normalizedSortBy = sortBy == null ? "expenseDate" : sortBy.trim();
        String sortField = SORT_FIELDS.get(normalizedSortBy);
        if (sortField == null) {
            throw new BadRequestException("Unsupported sortBy value");
        }

        String normalizedSortDir = sortDir == null ? SORT_DIRECTION_DESC : sortDir.trim().toLowerCase();
        if (!SORT_DIRECTION_ASC.equals(normalizedSortDir) && !SORT_DIRECTION_DESC.equals(normalizedSortDir)) {
            throw new BadRequestException("Unsupported sortDir value");
        }

        Sort.Direction direction = SORT_DIRECTION_ASC.equals(normalizedSortDir) ? Sort.Direction.ASC : Sort.Direction.DESC;
        return Sort.by(new Sort.Order(direction, sortField), new Sort.Order(Sort.Direction.DESC, "id"));
    }

    private void validateQueryParams(ExpenseQueryParams queryParams) {
        validateRanges(
                queryParams.startDate(),
                queryParams.endDate(),
                queryParams.minAmount(),
                queryParams.maxAmount()
        );
    }

    private void validateRanges(LocalDate startDate, LocalDate endDate, BigDecimal minAmount, BigDecimal maxAmount) {
        if (startDate != null && endDate != null && startDate.isAfter(endDate)) {
            throw new BadRequestException("startDate must be before or equal to endDate");
        }
        if (minAmount != null && maxAmount != null && minAmount.compareTo(maxAmount) > 0) {
            throw new BadRequestException("minAmount must be less than or equal to maxAmount");
        }
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}

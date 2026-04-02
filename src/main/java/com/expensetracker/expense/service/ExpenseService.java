package com.expensetracker.expense.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.dto.PagedResponse;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.expense.repository.ExpenseSpecifications;
import com.expensetracker.smartcategory.service.SmartCategoryService;
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
public class ExpenseService {

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
    private final SmartCategoryService smartCategoryService;

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

    @Transactional
    public ExpenseResponse createExpense(ExpenseRequest request, User user) {
        Category category = resolveExpenseCategory(request, user);

        Expense expense = new Expense();
        expense.setUser(user);
        expense.setCategory(category);
        expense.setAmount(request.amount());
        expense.setExpenseDate(request.expenseDate());
        expense.setDescription(trimToNull(request.description()));
        expense.setPaymentMethod(request.paymentMethod());

        return ExpenseResponse.from(expenseRepository.save(expense));
    }

    @Transactional
    public ExpenseResponse updateExpense(Long expenseId, ExpenseRequest request, User user) {
        Expense expense = findUserExpense(expenseId, user.getId());
        Category category = resolveExpenseCategory(request, user);

        expense.setCategory(category);
        expense.setAmount(request.amount());
        expense.setExpenseDate(request.expenseDate());
        expense.setDescription(trimToNull(request.description()));
        expense.setPaymentMethod(request.paymentMethod());

        return ExpenseResponse.from(expense);
    }

    @Transactional
    public void deleteExpense(Long expenseId, User user) {
        Expense expense = findUserExpense(expenseId, user.getId());
        expenseRepository.delete(expense);
    }

    private Expense findUserExpense(Long expenseId, Long userId) {
        return expenseRepository.findByIdAndUserId(expenseId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Expense not found"));
    }

    private Specification<Expense> buildSpecification(Long userId, ExpenseQueryParams queryParams) {
        Specification<Expense> specification = Specification.where(ExpenseSpecifications.hasUserId(userId));

        if (queryParams.categoryId() != null) {
            specification = specification.and(ExpenseSpecifications.hasCategoryId(queryParams.categoryId()));
        }
        if (queryParams.startDate() != null) {
            specification = specification.and(ExpenseSpecifications.expenseDateGreaterThanOrEqualTo(queryParams.startDate()));
        }
        if (queryParams.endDate() != null) {
            specification = specification.and(ExpenseSpecifications.expenseDateLessThanOrEqualTo(queryParams.endDate()));
        }
        if (queryParams.minAmount() != null) {
            specification = specification.and(ExpenseSpecifications.amountGreaterThanOrEqualTo(queryParams.minAmount()));
        }
        if (queryParams.maxAmount() != null) {
            specification = specification.and(ExpenseSpecifications.amountLessThanOrEqualTo(queryParams.maxAmount()));
        }
        if (hasText(queryParams.search())) {
            specification = specification.and(ExpenseSpecifications.matchesSearchTerm(queryParams.search().trim()));
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
        LocalDate startDate = queryParams.startDate();
        LocalDate endDate = queryParams.endDate();
        BigDecimal minAmount = queryParams.minAmount();
        BigDecimal maxAmount = queryParams.maxAmount();

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

    private Category resolveExpenseCategory(ExpenseRequest request, User user) {
        if (request.categoryId() != null) {
            return categoryService.getAccessibleCategory(request.categoryId(), user.getId());
        }

        return smartCategoryService.suggestCategory(request.description(), user.getId())
                .orElseThrow(() -> new BadRequestException(
                        "Category id is required unless a smart category rule matches the description"
                ));
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }

        String trimmedValue = value.trim();
        return trimmedValue.isEmpty() ? null : trimmedValue;
    }
}

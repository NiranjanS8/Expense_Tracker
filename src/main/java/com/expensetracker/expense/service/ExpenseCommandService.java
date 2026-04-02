package com.expensetracker.expense.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.smartcategory.service.SmartCategoryService;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ExpenseCommandService {

    private final ExpenseRepository expenseRepository;
    private final CategoryService categoryService;
    private final SmartCategoryService smartCategoryService;
    private final ExpenseQueryService expenseQueryService;

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
        Expense expense = expenseQueryService.findUserExpense(expenseId, user.getId());
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
        Expense expense = expenseQueryService.findUserExpense(expenseId, user.getId());
        expenseRepository.delete(expense);
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

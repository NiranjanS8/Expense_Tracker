package com.expensetracker.expense.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.dto.ExpenseRequest;
import com.expensetracker.expense.dto.ExpenseResponse;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.User;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ExpenseService {

    private final ExpenseRepository expenseRepository;
    private final CategoryService categoryService;

    @Transactional(readOnly = true)
    public List<ExpenseResponse> getExpenses(User user) {
        return expenseRepository.findAllByUserIdOrderByExpenseDateDescIdDesc(user.getId())
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
        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());

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
        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());

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

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }

        String trimmedValue = value.trim();
        return trimmedValue.isEmpty() ? null : trimmedValue;
    }
}

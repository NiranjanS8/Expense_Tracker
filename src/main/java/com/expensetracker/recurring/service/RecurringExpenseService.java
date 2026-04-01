package com.expensetracker.recurring.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.recurring.dto.RecurringExpenseRequest;
import com.expensetracker.recurring.dto.RecurringExpenseResponse;
import com.expensetracker.recurring.dto.RecurringGenerationResponse;
import com.expensetracker.recurring.entity.RecurringExpense;
import com.expensetracker.recurring.entity.RecurringFrequency;
import com.expensetracker.recurring.repository.RecurringExpenseRepository;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

@Service
@RequiredArgsConstructor
public class RecurringExpenseService {

    private final RecurringExpenseRepository recurringExpenseRepository;
    private final ExpenseRepository expenseRepository;
    private final CategoryService categoryService;

    @Transactional(readOnly = true)
    public List<RecurringExpenseResponse> getRecurringExpenses(User user) {
        return recurringExpenseRepository.findAllByUserIdOrderByCreatedAtDesc(user.getId())
                .stream()
                .map(RecurringExpenseResponse::from)
                .toList();
    }

    @Transactional
    public RecurringExpenseResponse createRecurringExpense(RecurringExpenseRequest request, User user) {
        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());

        RecurringExpense recurringExpense = new RecurringExpense();
        recurringExpense.setUser(user);
        recurringExpense.setCategory(category);
        recurringExpense.setAmount(request.amount());
        recurringExpense.setStartDate(request.startDate());
        recurringExpense.setNextExecutionDate(request.startDate());
        recurringExpense.setDescription(trimToNull(request.description()));
        recurringExpense.setPaymentMethod(request.paymentMethod());
        recurringExpense.setFrequency(request.frequency());
        recurringExpense.setActive(true);

        return RecurringExpenseResponse.from(recurringExpenseRepository.save(recurringExpense));
    }

    @Transactional
    public RecurringExpenseResponse updateRecurringExpense(Long recurringExpenseId, RecurringExpenseRequest request, User user) {
        RecurringExpense recurringExpense = findRecurringExpense(recurringExpenseId, user.getId());
        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());

        recurringExpense.setCategory(category);
        recurringExpense.setAmount(request.amount());
        recurringExpense.setStartDate(request.startDate());
        recurringExpense.setDescription(trimToNull(request.description()));
        recurringExpense.setPaymentMethod(request.paymentMethod());
        recurringExpense.setFrequency(request.frequency());
        if (recurringExpense.getNextExecutionDate().isBefore(request.startDate())) {
            recurringExpense.setNextExecutionDate(request.startDate());
        }

        return RecurringExpenseResponse.from(recurringExpense);
    }

    @Transactional
    public RecurringExpenseResponse updateRecurringExpenseStatus(Long recurringExpenseId, boolean active, User user) {
        RecurringExpense recurringExpense = findRecurringExpense(recurringExpenseId, user.getId());
        recurringExpense.setActive(active);
        return RecurringExpenseResponse.from(recurringExpense);
    }

    @Transactional
    public RecurringGenerationResponse generateDueRecurringExpensesForUser(LocalDate runDate, User user) {
        List<RecurringExpense> recurringExpenses = recurringExpenseRepository.findAllByUserIdOrderByCreatedAtDesc(user.getId())
                .stream()
                .filter(RecurringExpense::isActive)
                .filter(expense -> !expense.getNextExecutionDate().isAfter(runDate))
                .toList();

        int generatedExpenses = generateExpenses(recurringExpenses, runDate);
        return new RecurringGenerationResponse(runDate, recurringExpenses.size(), generatedExpenses);
    }

    @Scheduled(cron = "${app.recurring.generation.cron:0 0 1 * * *}")
    @Transactional
    public void generateScheduledRecurringExpenses() {
        generateExpenses(
                recurringExpenseRepository.findAllByActiveTrueAndNextExecutionDateLessThanEqual(LocalDate.now()),
                LocalDate.now()
        );
    }

    private int generateExpenses(List<RecurringExpense> recurringExpenses, LocalDate runDate) {
        int generatedExpenses = 0;

        for (RecurringExpense recurringExpense : recurringExpenses) {
            while (!recurringExpense.getNextExecutionDate().isAfter(runDate)) {
                if (!expenseRepository.existsByRecurringExpenseIdAndExpenseDate(
                        recurringExpense.getId(),
                        recurringExpense.getNextExecutionDate()
                )) {
                    Expense expense = new Expense();
                    expense.setUser(recurringExpense.getUser());
                    expense.setCategory(recurringExpense.getCategory());
                    expense.setAmount(recurringExpense.getAmount());
                    expense.setExpenseDate(recurringExpense.getNextExecutionDate());
                    expense.setDescription(recurringExpense.getDescription());
                    expense.setPaymentMethod(recurringExpense.getPaymentMethod());
                    expense.setRecurringExpense(recurringExpense);
                    expenseRepository.save(expense);
                    generatedExpenses++;
                }

                recurringExpense.setNextExecutionDate(nextExecutionDate(
                        recurringExpense.getNextExecutionDate(),
                        recurringExpense.getFrequency()
                ));
            }
        }

        return generatedExpenses;
    }

    private LocalDate nextExecutionDate(LocalDate currentDate, RecurringFrequency frequency) {
        return switch (frequency) {
            case WEEKLY -> currentDate.plusWeeks(1);
            case MONTHLY -> currentDate.plusMonths(1);
        };
    }

    private RecurringExpense findRecurringExpense(Long recurringExpenseId, Long userId) {
        return recurringExpenseRepository.findByIdAndUserId(recurringExpenseId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Recurring expense not found"));
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }

        String trimmedValue = value.trim();
        return trimmedValue.isEmpty() ? null : trimmedValue;
    }
}

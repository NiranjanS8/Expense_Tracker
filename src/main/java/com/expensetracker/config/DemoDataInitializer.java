package com.expensetracker.config;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.repository.CategoryRepository;
import com.expensetracker.expense.entity.Expense;
import com.expensetracker.expense.entity.PaymentMethod;
import com.expensetracker.expense.repository.ExpenseRepository;
import com.expensetracker.user.entity.Role;
import com.expensetracker.user.entity.User;
import com.expensetracker.user.repository.UserRepository;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
@RequiredArgsConstructor
public class DemoDataInitializer {

    private final PasswordEncoder passwordEncoder;

    @Bean
    @ConditionalOnProperty(name = "app.seed.enabled", havingValue = "true", matchIfMissing = true)
    public CommandLineRunner initializeDemoData(
            UserRepository userRepository,
            CategoryRepository categoryRepository,
            ExpenseRepository expenseRepository
    ) {
        return args -> {
            User demoUser = userRepository.findByEmailIgnoreCase("demo@expensetracker.com")
                    .orElseGet(() -> createDemoUser(userRepository));

            createUserCategoryIfMissing(categoryRepository, demoUser, "Pets");
            createUserCategoryIfMissing(categoryRepository, demoUser, "Home Office");

            if (expenseRepository.countByUserId(demoUser.getId()) == 0) {
                List<Expense> expenses = List.of(
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Food", demoUser.getId()),
                                "Lunch with team", "420.00", LocalDate.now().minusDays(1), PaymentMethod.UPI),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Transport", demoUser.getId()),
                                "Metro recharge", "799.00", LocalDate.now().minusDays(2), PaymentMethod.CARD),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Bills", demoUser.getId()),
                                "Electricity bill", "1850.00", LocalDate.now().minusDays(4), PaymentMethod.BANK_TRANSFER),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Shopping", demoUser.getId()),
                                "Groceries", "2360.75", LocalDate.now().minusDays(6), PaymentMethod.CARD),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Entertainment", demoUser.getId()),
                                "Movie tickets", "680.00", LocalDate.now().minusDays(8), PaymentMethod.UPI),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Health", demoUser.getId()),
                                "Pharmacy order", "540.50", LocalDate.now().minusDays(11), PaymentMethod.WALLET),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Travel", demoUser.getId()),
                                "Weekend cab", "1240.00", LocalDate.now().minusDays(15), PaymentMethod.CARD),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Education", demoUser.getId()),
                                "Online course", "3499.00", LocalDate.now().minusDays(22), PaymentMethod.CARD),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Pets", demoUser.getId()),
                                "Dog food", "950.00", LocalDate.now().minusDays(27), PaymentMethod.UPI),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Home Office", demoUser.getId()),
                                "Laptop stand", "1299.00", LocalDate.now().minusDays(35), PaymentMethod.CARD),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Food", demoUser.getId()),
                                "Dinner order", "760.00", LocalDate.now().minusDays(43), PaymentMethod.UPI),
                        buildExpense(demoUser, getRequiredCategory(categoryRepository, "Other", demoUser.getId()),
                                "Gift wrap", "150.00", LocalDate.now().minusDays(52), PaymentMethod.CASH)
                );

                expenseRepository.saveAll(expenses);
            }
        };
    }

    private User createDemoUser(UserRepository userRepository) {
        User user = new User();
        user.setFullName("Demo User");
        user.setEmail("demo@expensetracker.com");
        user.setPassword(passwordEncoder.encode("Password@123"));
        user.setRole(Role.USER);
        return userRepository.save(user);
    }

    private void createUserCategoryIfMissing(CategoryRepository categoryRepository, User user, String categoryName) {
        categoryRepository.findByOwnerIdAndNameIgnoreCase(user.getId(), categoryName)
                .or(() -> categoryRepository.findBySystemDefinedTrueAndNameIgnoreCase(categoryName))
                .orElseGet(() -> {
                    Category category = new Category();
                    category.setName(categoryName);
                    category.setSystemDefined(false);
                    category.setOwner(user);
                    return categoryRepository.save(category);
                });
    }

    private Category getRequiredCategory(CategoryRepository categoryRepository, String categoryName, Long userId) {
        return categoryRepository.findByOwnerIdAndNameIgnoreCase(userId, categoryName)
                .or(() -> categoryRepository.findBySystemDefinedTrueAndNameIgnoreCase(categoryName))
                .orElseThrow(() -> new IllegalStateException("Missing category: " + categoryName));
    }

    private Expense buildExpense(
            User user,
            Category category,
            String description,
            String amount,
            LocalDate expenseDate,
            PaymentMethod paymentMethod
    ) {
        Expense expense = new Expense();
        expense.setUser(user);
        expense.setCategory(category);
        expense.setDescription(description);
        expense.setAmount(new BigDecimal(amount));
        expense.setExpenseDate(expenseDate);
        expense.setPaymentMethod(paymentMethod);
        return expense;
    }
}

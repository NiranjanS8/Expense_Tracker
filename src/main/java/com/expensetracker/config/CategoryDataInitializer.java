package com.expensetracker.config;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.repository.CategoryRepository;
import java.util.List;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class CategoryDataInitializer {

    @Bean
    public CommandLineRunner initializeCategories(CategoryRepository categoryRepository) {
        return args -> {
            List<String> defaultCategories = List.of(
                    "Food",
                    "Transport",
                    "Shopping",
                    "Bills",
                    "Health",
                    "Entertainment",
                    "Travel",
                    "Education",
                    "Other"
            );

            for (String categoryName : defaultCategories) {
                if (!categoryRepository.existsBySystemDefinedTrueAndNameIgnoreCase(categoryName)) {
                    Category category = new Category();
                    category.setName(categoryName);
                    category.setSystemDefined(true);
                    categoryRepository.save(category);
                }
            }
        };
    }
}

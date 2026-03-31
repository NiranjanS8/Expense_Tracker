package com.expensetracker.category.service;

import com.expensetracker.category.dto.CategoryRequest;
import com.expensetracker.category.dto.CategoryResponse;
import com.expensetracker.category.entity.Category;
import com.expensetracker.category.repository.CategoryRepository;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.user.entity.User;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class CategoryService {

    private final CategoryRepository categoryRepository;

    @Transactional(readOnly = true)
    public List<CategoryResponse> getCategories(User user) {
        return categoryRepository.findBySystemDefinedTrueOrOwnerIdOrderByNameAsc(user.getId())
                .stream()
                .map(CategoryResponse::from)
                .toList();
    }

    @Transactional
    public CategoryResponse createCategory(CategoryRequest request, User user) {
        String normalizedName = request.name().trim();
        if (categoryRepository.existsBySystemDefinedTrueAndNameIgnoreCase(normalizedName)
                || categoryRepository.existsByOwnerIdAndNameIgnoreCase(user.getId(), normalizedName)) {
            throw new BadRequestException("Category with this name already exists");
        }

        Category category = new Category();
        category.setName(normalizedName);
        category.setSystemDefined(false);
        category.setOwner(user);

        return CategoryResponse.from(categoryRepository.save(category));
    }

    @Transactional(readOnly = true)
    public Category getAccessibleCategory(Long categoryId, Long userId) {
        return categoryRepository.findByIdAndSystemDefinedTrueOrIdAndOwnerId(categoryId, categoryId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found"));
    }
}

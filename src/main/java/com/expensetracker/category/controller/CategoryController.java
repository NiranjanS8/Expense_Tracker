package com.expensetracker.category.controller;

import com.expensetracker.category.dto.CategoryRequest;
import com.expensetracker.category.dto.CategoryResponse;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/categories")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryService categoryService;

    @GetMapping
    public List<CategoryResponse> getCategories(@AuthenticationPrincipal User user) {
        return categoryService.getCategories(user);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CategoryResponse createCategory(
            @Valid @RequestBody CategoryRequest request,
            @AuthenticationPrincipal User user
    ) {
        return categoryService.createCategory(request, user);
    }
}

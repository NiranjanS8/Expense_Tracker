package com.expensetracker.smartcategory.service;

import com.expensetracker.category.entity.Category;
import com.expensetracker.category.service.CategoryService;
import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.smartcategory.dto.SmartCategoryRuleRequest;
import com.expensetracker.smartcategory.dto.SmartCategoryRuleResponse;
import com.expensetracker.smartcategory.entity.SmartCategoryRule;
import com.expensetracker.smartcategory.repository.SmartCategoryRuleRepository;
import com.expensetracker.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class SmartCategoryService {

    private final SmartCategoryRuleRepository smartCategoryRuleRepository;
    private final CategoryService categoryService;

    @Transactional(readOnly = true)
    public List<SmartCategoryRuleResponse> getRules(User user) {
        return smartCategoryRuleRepository.findAllByUserIdOrderByKeywordAsc(user.getId())
                .stream()
                .map(SmartCategoryRuleResponse::from)
                .toList();
    }

    @Transactional
    public SmartCategoryRuleResponse createRule(SmartCategoryRuleRequest request, User user) {
        String normalizedKeyword = normalizeKeyword(request.keyword());
        if (smartCategoryRuleRepository.existsByUserIdAndKeywordIgnoreCase(user.getId(), normalizedKeyword)) {
            throw new BadRequestException("Smart category rule already exists for this keyword");
        }

        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());
        SmartCategoryRule rule = new SmartCategoryRule();
        rule.setUser(user);
        rule.setCategory(category);
        rule.setKeyword(normalizedKeyword);
        rule.setActive(request.active());

        return SmartCategoryRuleResponse.from(smartCategoryRuleRepository.save(rule));
    }

    @Transactional
    public SmartCategoryRuleResponse updateRule(Long ruleId, SmartCategoryRuleRequest request, User user) {
        SmartCategoryRule rule = findRule(ruleId, user.getId());
        String normalizedKeyword = normalizeKeyword(request.keyword());
        if (!rule.getKeyword().equalsIgnoreCase(normalizedKeyword)
                && smartCategoryRuleRepository.existsByUserIdAndKeywordIgnoreCase(user.getId(), normalizedKeyword)) {
            throw new BadRequestException("Smart category rule already exists for this keyword");
        }

        Category category = categoryService.getAccessibleCategory(request.categoryId(), user.getId());
        rule.setKeyword(normalizedKeyword);
        rule.setCategory(category);
        rule.setActive(request.active());

        return SmartCategoryRuleResponse.from(rule);
    }

    @Transactional
    public void deleteRule(Long ruleId, User user) {
        smartCategoryRuleRepository.delete(findRule(ruleId, user.getId()));
    }

    @Transactional(readOnly = true)
    public Optional<Category> suggestCategory(String description, Long userId) {
        if (description == null || description.trim().isEmpty()) {
            return Optional.empty();
        }

        String normalizedDescription = description.trim().toLowerCase();
        return smartCategoryRuleRepository.findAllByUserIdAndActiveTrueOrderByKeywordDesc(userId)
                .stream()
                .sorted(Comparator.comparingInt((SmartCategoryRule rule) -> rule.getKeyword().length()).reversed())
                .filter(rule -> normalizedDescription.contains(rule.getKeyword().toLowerCase()))
                .map(SmartCategoryRule::getCategory)
                .findFirst();
    }

    private SmartCategoryRule findRule(Long ruleId, Long userId) {
        return smartCategoryRuleRepository.findByIdAndUserId(ruleId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Smart category rule not found"));
    }

    private String normalizeKeyword(String keyword) {
        return keyword.trim().toLowerCase();
    }
}

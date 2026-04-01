package com.expensetracker.smartcategory.repository;

import com.expensetracker.smartcategory.entity.SmartCategoryRule;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SmartCategoryRuleRepository extends JpaRepository<SmartCategoryRule, Long> {

    List<SmartCategoryRule> findAllByUserIdOrderByKeywordAsc(Long userId);

    Optional<SmartCategoryRule> findByIdAndUserId(Long id, Long userId);

    boolean existsByUserIdAndKeywordIgnoreCase(Long userId, String keyword);

    List<SmartCategoryRule> findAllByUserIdAndActiveTrueOrderByKeywordDesc(Long userId);
}

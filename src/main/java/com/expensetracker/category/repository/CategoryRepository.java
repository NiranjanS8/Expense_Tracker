package com.expensetracker.category.repository;

import com.expensetracker.category.entity.Category;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CategoryRepository extends JpaRepository<Category, Long> {

    List<Category> findBySystemDefinedTrueOrOwnerIdOrderByNameAsc(Long ownerId);

    Optional<Category> findByIdAndSystemDefinedTrueOrIdAndOwnerId(Long systemCategoryId, Long ownedCategoryId, Long ownerId);

    boolean existsByOwnerIdAndNameIgnoreCase(Long ownerId, String name);

    boolean existsBySystemDefinedTrueAndNameIgnoreCase(String name);
}

package com.expensetracker.goals.repository;

import com.expensetracker.goals.entity.Goal;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface GoalRepository extends JpaRepository<Goal, Long> {

    List<Goal> findAllByUserIdOrderByTargetDateAscCreatedAtDesc(Long userId);

    Optional<Goal> findByIdAndUserId(Long id, Long userId);
}

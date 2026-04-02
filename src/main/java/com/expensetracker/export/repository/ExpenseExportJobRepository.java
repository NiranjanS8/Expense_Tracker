package com.expensetracker.export.repository;

import com.expensetracker.export.entity.ExpenseExportJob;
import com.expensetracker.export.entity.ExpenseExportJobStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExpenseExportJobRepository extends JpaRepository<ExpenseExportJob, Long> {

    Optional<ExpenseExportJob> findByIdAndUserId(Long id, Long userId);

    List<ExpenseExportJob> findAllByUserIdOrderByCreatedAtDesc(Long userId);

    List<ExpenseExportJob> findByStatusOrderByCreatedAtAsc(ExpenseExportJobStatus status, Pageable pageable);
}

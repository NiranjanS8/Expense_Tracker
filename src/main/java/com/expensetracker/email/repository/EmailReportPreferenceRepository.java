package com.expensetracker.email.repository;

import com.expensetracker.email.entity.EmailReportPreference;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface EmailReportPreferenceRepository extends JpaRepository<EmailReportPreference, Long> {

    Optional<EmailReportPreference> findByUserId(Long userId);

    List<EmailReportPreference> findAllByEnabledTrue();
}

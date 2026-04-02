package com.expensetracker.job.repository;

import com.expensetracker.job.entity.JobLock;
import org.springframework.data.jpa.repository.JpaRepository;

public interface JobLockRepository extends JpaRepository<JobLock, String> {
}

package com.expensetracker.job.service;

import com.expensetracker.job.entity.JobLock;
import com.expensetracker.job.repository.JobLockRepository;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobLockService {

    private final JobLockRepository jobLockRepository;

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Optional<String> tryAcquire(String lockName, Duration maxLockDuration, String ownerPrefix) {
        Instant now = Instant.now();
        String ownerToken = ownerPrefix + "-" + UUID.randomUUID();

        try {
            Optional<JobLock> existingLock = jobLockRepository.findById(lockName);
            if (existingLock.isEmpty()) {
                JobLock newLock = new JobLock();
                newLock.setName(lockName);
                newLock.setLockedAt(now);
                newLock.setLockedUntil(now.plus(maxLockDuration));
                newLock.setLockedBy(ownerToken);
                jobLockRepository.saveAndFlush(newLock);
                return Optional.of(ownerToken);
            }

            JobLock jobLock = existingLock.get();
            if (jobLock.getLockedUntil().isAfter(now)) {
                return Optional.empty();
            }

            jobLock.setLockedAt(now);
            jobLock.setLockedUntil(now.plus(maxLockDuration));
            jobLock.setLockedBy(ownerToken);
            jobLockRepository.saveAndFlush(jobLock);
            return Optional.of(ownerToken);
        } catch (DataIntegrityViolationException | ObjectOptimisticLockingFailureException exception) {
            return Optional.empty();
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void release(String lockName, String ownerToken) {
        jobLockRepository.findById(lockName).ifPresent(jobLock -> {
            if (!ownerToken.equals(jobLock.getLockedBy())) {
                return;
            }

            jobLock.setLockedUntil(Instant.now());
            jobLockRepository.save(jobLock);
        });
    }

    public boolean runWithLock(String lockName, Duration maxLockDuration, String ownerPrefix, Runnable job) {
        Optional<String> ownerToken = tryAcquire(lockName, maxLockDuration, ownerPrefix);
        if (ownerToken.isEmpty()) {
            log.info("Skipped job {} because another node already holds the lock.", lockName);
            return false;
        }

        try {
            job.run();
            return true;
        } finally {
            release(lockName, ownerToken.get());
        }
    }
}

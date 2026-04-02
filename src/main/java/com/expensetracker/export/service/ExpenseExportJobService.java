package com.expensetracker.export.service;

import com.expensetracker.common.exception.BadRequestException;
import com.expensetracker.common.exception.ResourceNotFoundException;
import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.export.config.ExportJobProperties;
import com.expensetracker.export.dto.ExpenseExportJobRequest;
import com.expensetracker.export.dto.ExpenseExportJobResponse;
import com.expensetracker.export.entity.ExpenseExportJob;
import com.expensetracker.export.entity.ExpenseExportJobStatus;
import com.expensetracker.export.repository.ExpenseExportJobRepository;
import com.expensetracker.job.service.JobLockService;
import com.expensetracker.observability.ObservabilityMetricsService;
import com.expensetracker.user.entity.User;
import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ExpenseExportJobService {

    private static final Logger logger = LoggerFactory.getLogger(ExpenseExportJobService.class);
    private static final String EXPORT_JOB_LOCK = "expense-export-job-processor";
    private static final Duration EXPORT_JOB_LOCK_DURATION = Duration.ofMinutes(10);

    private final ExpenseExportJobRepository expenseExportJobRepository;
    private final ExpenseExportService expenseExportService;
    private final ExportJobProperties exportJobProperties;
    private final JobLockService jobLockService;
    private final ObservabilityMetricsService observabilityMetricsService;

    private Path storageDirectory;

    @PostConstruct
    void initializeStorageDirectory() {
        storageDirectory = Path.of(exportJobProperties.storageDir()).toAbsolutePath().normalize();
        try {
            Files.createDirectories(storageDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException("Failed to initialize export storage directory", exception);
        }
    }

    @Transactional
    public ExpenseExportJobResponse createJob(User user, ExpenseExportJobRequest request) {
        ExpenseExportJob job = new ExpenseExportJob();
        job.setUser(user);
        job.setType(request.type());
        job.setStatus(ExpenseExportJobStatus.PENDING);
        job.setSortBy(normalizeSortBy(request.sortBy()));
        job.setSortDir(normalizeSortDir(request.sortDir()));
        job.setSearch(normalizeSearch(request.search()));
        job.setCategoryId(request.categoryId());
        job.setStartDate(request.startDate());
        job.setEndDate(request.endDate());
        job.setMinAmount(request.minAmount());
        job.setMaxAmount(request.maxAmount());

        ExpenseExportJob savedJob = expenseExportJobRepository.save(job);
        observabilityMetricsService.incrementExportJobCreated(savedJob.getType().name().toLowerCase());
        logger.info(
                "event=export_job_created jobId={} userId={} type={} status={}",
                savedJob.getId(),
                user.getId(),
                savedJob.getType(),
                savedJob.getStatus()
        );
        return ExpenseExportJobResponse.from(savedJob);
    }

    @Transactional(readOnly = true)
    public List<ExpenseExportJobResponse> getJobs(User user) {
        return expenseExportJobRepository.findAllByUserIdOrderByCreatedAtDesc(user.getId())
                .stream()
                .map(ExpenseExportJobResponse::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public ExpenseExportJobResponse getJob(User user, Long jobId) {
        return ExpenseExportJobResponse.from(getUserJob(jobId, user.getId()));
    }

    @Transactional(readOnly = true)
    public byte[] downloadJobFile(User user, Long jobId) {
        ExpenseExportJob job = getUserJob(jobId, user.getId());
        if (job.getStatus() != ExpenseExportJobStatus.COMPLETED || job.getStoredFileName() == null) {
            throw new BadRequestException("Export job is not ready for download");
        }

        try {
            return Files.readAllBytes(resolveStoredFile(job.getStoredFileName()));
        } catch (IOException exception) {
            throw new ResourceNotFoundException("Export file not found");
        }
    }

    @Transactional(readOnly = true)
    public ExpenseExportJob getUserJob(Long jobId, Long userId) {
        return expenseExportJobRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Export job not found"));
    }

    @Scheduled(fixedDelayString = "${app.exports.jobs.poll-interval-ms:10000}")
    public void processScheduledJobs() {
        jobLockService.runWithLock(
                EXPORT_JOB_LOCK,
                EXPORT_JOB_LOCK_DURATION,
                "export-job",
                this::processPendingJobs
        );
    }

    public void processPendingJobs() {
        List<ExpenseExportJob> pendingJobs = expenseExportJobRepository
                .findByStatusOrderByCreatedAtAsc(
                        ExpenseExportJobStatus.PENDING,
                        PageRequest.of(0, exportJobProperties.batchSize())
                );

        if (pendingJobs.isEmpty()) {
            return;
        }

        logger.info("event=export_job_batch_started pendingJobs={}", pendingJobs.size());
        for (ExpenseExportJob pendingJob : pendingJobs) {
            processSingleJob(pendingJob.getId());
        }
        logger.info("event=export_job_batch_completed pendingJobs={}", pendingJobs.size());
    }

    @Transactional
    protected void processSingleJob(Long jobId) {
        ExpenseExportJob job = expenseExportJobRepository.findById(jobId)
                .orElseThrow(() -> new ResourceNotFoundException("Export job not found"));

        if (job.getStatus() != ExpenseExportJobStatus.PENDING) {
            return;
        }

        long startTime = System.nanoTime();
        job.setStatus(ExpenseExportJobStatus.PROCESSING);
        job.setStartedAt(Instant.now());
        job.setErrorMessage(null);
        expenseExportJobRepository.save(job);
        logger.info(
                "event=export_job_started jobId={} userId={} type={}",
                job.getId(),
                job.getUser().getId(),
                job.getType()
        );

        try {
            byte[] exportBytes = expenseExportService.exportExpenses(
                    job.getUser(),
                    new ExpenseQueryParams(
                            0,
                            Integer.MAX_VALUE,
                            job.getSortBy(),
                            job.getSortDir(),
                            job.getSearch(),
                            job.getCategoryId(),
                            job.getStartDate(),
                            job.getEndDate(),
                            job.getMinAmount(),
                            job.getMaxAmount()
                    ),
                    job.getType()
            );

            String storedFileName = buildStoredFileName(job);
            Files.write(
                    resolveStoredFile(storedFileName),
                    exportBytes,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.TRUNCATE_EXISTING,
                    StandardOpenOption.WRITE
            );

            job.setStatus(ExpenseExportJobStatus.COMPLETED);
            job.setStoredFileName(storedFileName);
            job.setFileName(buildDownloadFileName(job));
            job.setContentType(job.getType().contentType());
            job.setCompletedAt(Instant.now());
            expenseExportJobRepository.save(job);

            observabilityMetricsService.recordExportJobProcessed(
                    job.getType().name().toLowerCase(),
                    "success",
                    System.nanoTime() - startTime,
                    exportBytes.length
            );
            logger.info(
                    "event=export_job_completed jobId={} userId={} type={} fileName={} fileSizeBytes={} durationMs={}",
                    job.getId(),
                    job.getUser().getId(),
                    job.getType(),
                    job.getFileName(),
                    exportBytes.length,
                    (System.nanoTime() - startTime) / 1_000_000
            );
        } catch (Exception exception) {
            observabilityMetricsService.recordExportJobProcessed(
                    job.getType().name().toLowerCase(),
                    "failure",
                    System.nanoTime() - startTime,
                    -1
            );
            job.setStatus(ExpenseExportJobStatus.FAILED);
            job.setErrorMessage(exception.getMessage());
            job.setCompletedAt(Instant.now());
            expenseExportJobRepository.save(job);
            logger.error(
                    "event=export_job_failed jobId={} userId={} type={} durationMs={} error={}",
                    job.getId(),
                    job.getUser().getId(),
                    job.getType(),
                    (System.nanoTime() - startTime) / 1_000_000,
                    exception.getMessage(),
                    exception
            );
        }
    }

    private Path resolveStoredFile(String storedFileName) {
        return storageDirectory.resolve(storedFileName).normalize();
    }

    private String buildStoredFileName(ExpenseExportJob job) {
        return "expense-export-" + job.getId() + "." + job.getType().fileExtension();
    }

    private String buildDownloadFileName(ExpenseExportJob job) {
        return "expenses-" + job.getCreatedAt().toEpochMilli() + "." + job.getType().fileExtension();
    }

    private String normalizeSortBy(String sortBy) {
        return sortBy == null || sortBy.trim().isEmpty() ? "expenseDate" : sortBy.trim();
    }

    private String normalizeSortDir(String sortDir) {
        return sortDir == null || sortDir.trim().isEmpty() ? "desc" : sortDir.trim();
    }

    private String normalizeSearch(String search) {
        if (search == null || search.trim().isEmpty()) {
            return null;
        }
        return search.trim();
    }
}

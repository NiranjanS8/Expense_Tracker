package com.expensetracker.export.dto;

import com.expensetracker.export.entity.ExpenseExportJob;
import com.expensetracker.export.entity.ExpenseExportJobStatus;
import com.expensetracker.export.entity.ExpenseExportJobType;
import java.time.Instant;

public record ExpenseExportJobResponse(
        Long id,
        ExpenseExportJobType type,
        ExpenseExportJobStatus status,
        String fileName,
        String contentType,
        String errorMessage,
        boolean downloadReady,
        Instant createdAt,
        Instant startedAt,
        Instant completedAt
) {

    public static ExpenseExportJobResponse from(ExpenseExportJob job) {
        return new ExpenseExportJobResponse(
                job.getId(),
                job.getType(),
                job.getStatus(),
                job.getFileName(),
                job.getContentType(),
                job.getErrorMessage(),
                job.getStatus() == ExpenseExportJobStatus.COMPLETED && job.getStoredFileName() != null,
                job.getCreatedAt(),
                job.getStartedAt(),
                job.getCompletedAt()
        );
    }
}

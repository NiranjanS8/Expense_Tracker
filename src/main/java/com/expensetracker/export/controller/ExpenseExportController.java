package com.expensetracker.export.controller;

import com.expensetracker.export.dto.ExpenseExportJobRequest;
import com.expensetracker.export.dto.ExpenseExportJobResponse;
import com.expensetracker.export.service.ExpenseExportJobService;
import com.expensetracker.security.RateLimitService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@Validated
@RequestMapping("/exports")
public class ExpenseExportController {

    private final ExpenseExportJobService expenseExportJobService;
    private final RateLimitService rateLimitService;

    public ExpenseExportController(
            ExpenseExportJobService expenseExportJobService,
            RateLimitService rateLimitService
    ) {
        this.expenseExportJobService = expenseExportJobService;
        this.rateLimitService = rateLimitService;
    }

    @PostMapping("/jobs")
    public ResponseEntity<ExpenseExportJobResponse> createExportJob(
            @AuthenticationPrincipal User user,
            @Valid @RequestBody ExpenseExportJobRequest request
    ) {
        rateLimitService.checkExportJobRateLimit(user);
        return ResponseEntity.accepted().body(expenseExportJobService.createJob(user, request));
    }

    @GetMapping("/jobs")
    public ResponseEntity<List<ExpenseExportJobResponse>> getExportJobs(@AuthenticationPrincipal User user) {
        return ResponseEntity.ok(expenseExportJobService.getJobs(user));
    }

    @GetMapping("/jobs/{jobId}")
    public ResponseEntity<ExpenseExportJobResponse> getExportJob(
            @AuthenticationPrincipal User user,
            @PathVariable Long jobId
    ) {
        return ResponseEntity.ok(expenseExportJobService.getJob(user, jobId));
    }

    @GetMapping("/jobs/{jobId}/download")
    public ResponseEntity<byte[]> downloadExportJob(
            @AuthenticationPrincipal User user,
            @PathVariable Long jobId
    ) {
        ExpenseExportJobResponse job = expenseExportJobService.getJob(user, jobId);
        byte[] fileContent = expenseExportJobService.downloadJobFile(user, jobId);

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(job.fileName())
                        .build()
                        .toString())
                .contentType(MediaType.parseMediaType(job.contentType()))
                .body(fileContent);
    }

    @GetMapping("/expenses/csv")
    public ResponseEntity<Void> retiredSynchronousCsvExport() {
        throw new ResponseStatusException(
                HttpStatus.GONE,
                "Synchronous export endpoints were removed. Create an async export job at /exports/jobs instead."
        );
    }

    @GetMapping("/expenses/pdf")
    public ResponseEntity<Void> retiredSynchronousPdfExport() {
        throw new ResponseStatusException(
                HttpStatus.GONE,
                "Synchronous export endpoints were removed. Create an async export job at /exports/jobs instead."
        );
    }
}

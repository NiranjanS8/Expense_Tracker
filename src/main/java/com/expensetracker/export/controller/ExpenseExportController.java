package com.expensetracker.export.controller;

import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.export.dto.ExpenseExportJobRequest;
import com.expensetracker.export.dto.ExpenseExportJobResponse;
import com.expensetracker.export.service.ExpenseExportJobService;
import com.expensetracker.export.service.ExpenseExportService;
import com.expensetracker.user.entity.User;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
@RequestMapping("/exports")
public class ExpenseExportController {

    private final ExpenseExportService expenseExportService;
    private final ExpenseExportJobService expenseExportJobService;

    public ExpenseExportController(
            ExpenseExportService expenseExportService,
            ExpenseExportJobService expenseExportJobService
    ) {
        this.expenseExportService = expenseExportService;
        this.expenseExportJobService = expenseExportJobService;
    }

    @PostMapping("/jobs")
    public ResponseEntity<ExpenseExportJobResponse> createExportJob(
            @AuthenticationPrincipal User user,
            @Valid @RequestBody ExpenseExportJobRequest request
    ) {
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

    @GetMapping(value = "/expenses/csv", produces = "text/csv")
    public ResponseEntity<byte[]> exportExpensesAsCsv(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "expenseDate") String sortBy,
            @RequestParam(defaultValue = "desc") String sortDir,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate,
            @RequestParam(required = false) @DecimalMin(value = "0.0", inclusive = true,
                    message = "minAmount must be zero or greater") BigDecimal minAmount,
            @RequestParam(required = false) @DecimalMin(value = "0.0", inclusive = true,
                    message = "maxAmount must be zero or greater") BigDecimal maxAmount
    ) {
        byte[] csv = expenseExportService.exportExpensesAsCsv(
                user,
                new ExpenseQueryParams(0, Integer.MAX_VALUE, sortBy, sortDir, search, categoryId, startDate, endDate,
                        minAmount, maxAmount)
        );

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename("expenses.csv")
                        .build()
                        .toString())
                .contentType(MediaType.parseMediaType("text/csv"))
                .body(csv);
    }

    @GetMapping(value = "/expenses/pdf", produces = MediaType.APPLICATION_PDF_VALUE)
    public ResponseEntity<byte[]> exportExpensesAsPdf(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "expenseDate") String sortBy,
            @RequestParam(defaultValue = "desc") String sortDir,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate,
            @RequestParam(required = false) @DecimalMin(value = "0.0", inclusive = true,
                    message = "minAmount must be zero or greater") BigDecimal minAmount,
            @RequestParam(required = false) @DecimalMin(value = "0.0", inclusive = true,
                    message = "maxAmount must be zero or greater") BigDecimal maxAmount
    ) {
        byte[] pdf = expenseExportService.exportExpensesAsPdf(
                user,
                new ExpenseQueryParams(0, Integer.MAX_VALUE, sortBy, sortDir, search, categoryId, startDate, endDate,
                        minAmount, maxAmount)
        );

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename("expenses.pdf")
                        .build()
                        .toString())
                .contentType(MediaType.APPLICATION_PDF)
                .body(pdf);
    }
}

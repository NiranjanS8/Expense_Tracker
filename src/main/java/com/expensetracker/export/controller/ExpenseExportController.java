package com.expensetracker.export.controller;

import com.expensetracker.expense.dto.ExpenseQueryParams;
import com.expensetracker.export.service.ExpenseExportService;
import com.expensetracker.user.entity.User;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDate;

@RestController
@Validated
@RequestMapping("/exports/expenses")
public class ExpenseExportController {

    private final ExpenseExportService expenseExportService;

    public ExpenseExportController(ExpenseExportService expenseExportService) {
        this.expenseExportService = expenseExportService;
    }

    @GetMapping(value = "/csv", produces = "text/csv")
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

    @GetMapping(value = "/pdf", produces = MediaType.APPLICATION_PDF_VALUE)
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

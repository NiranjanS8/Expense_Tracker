package com.expensetracker.export.entity;

import com.expensetracker.common.entity.BaseEntity;
import com.expensetracker.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "expense_export_jobs")
public class ExpenseExportJob extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ExpenseExportJobType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ExpenseExportJobStatus status;

    @Column(nullable = false, length = 50)
    private String sortBy;

    @Column(nullable = false, length = 10)
    private String sortDir;

    @Column(length = 255)
    private String search;

    private Long categoryId;

    private LocalDate startDate;

    private LocalDate endDate;

    @Column(precision = 19, scale = 2)
    private BigDecimal minAmount;

    @Column(precision = 19, scale = 2)
    private BigDecimal maxAmount;

    @Column(length = 255)
    private String fileName;

    @Column(length = 255)
    private String storedFileName;

    @Column(length = 100)
    private String contentType;

    @Column(length = 500)
    private String errorMessage;

    private Instant startedAt;

    private Instant completedAt;
}

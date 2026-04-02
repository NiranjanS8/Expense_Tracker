package com.expensetracker.job.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "job_locks")
public class JobLock {

    @Id
    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false)
    private Instant lockedUntil;

    @Column(nullable = false)
    private Instant lockedAt;

    @Column(nullable = false, length = 100)
    private String lockedBy;

    @Version
    private Long version;
}

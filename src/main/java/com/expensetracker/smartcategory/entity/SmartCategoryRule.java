package com.expensetracker.smartcategory.entity;

import com.expensetracker.category.entity.Category;
import com.expensetracker.common.entity.BaseEntity;
import com.expensetracker.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(
        name = "smart_category_rules",
        uniqueConstraints = {
                @UniqueConstraint(name = "uk_smart_category_rule_user_keyword", columnNames = {"user_id", "keyword"})
        }
)
public class SmartCategoryRule extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "category_id", nullable = false)
    private Category category;

    @Column(nullable = false, length = 100)
    private String keyword;

    @Column(nullable = false)
    private boolean active;
}

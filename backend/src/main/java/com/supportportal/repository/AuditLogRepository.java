package com.supportportal.repository;

import com.supportportal.entity.AuditLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

    @Query("SELECT a FROM AuditLog a WHERE " +
           "(:search IS NULL OR LOWER(a.action) LIKE LOWER(CONCAT('%',:search,'%')) OR " +
           "LOWER(a.entityType) LIKE LOWER(CONCAT('%',:search,'%'))) " +
           "AND (:userId IS NULL OR a.user.id = :userId)")
    Page<AuditLog> searchAuditLogs(@Param("search") String search,
                                   @Param("userId") Long userId,
                                   Pageable pageable);
}

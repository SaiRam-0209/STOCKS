package com.supportportal.repository;

import com.supportportal.entity.AIResponse;
import com.supportportal.enums.AIResponseStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AIResponseRepository extends JpaRepository<AIResponse, Long> {
    List<AIResponse> findByTicketIdOrderByCreatedAtDesc(Long ticketId);
    Page<AIResponse> findByStatus(AIResponseStatus status, Pageable pageable);
    long countByStatus(AIResponseStatus status);
}

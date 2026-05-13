package com.supportportal.repository;

import com.supportportal.entity.ChatMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
    List<ChatMessage> findByTicketIdOrderByCreatedAtAsc(Long ticketId);
    long countByTicketId(Long ticketId);
}

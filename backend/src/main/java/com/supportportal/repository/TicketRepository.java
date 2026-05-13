package com.supportportal.repository;

import com.supportportal.entity.Ticket;
import com.supportportal.entity.User;
import com.supportportal.enums.TicketCategory;
import com.supportportal.enums.TicketPriority;
import com.supportportal.enums.TicketStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public interface TicketRepository extends JpaRepository<Ticket, Long> {

    Optional<Ticket> findByTicketNumber(String ticketNumber);

    Page<Ticket> findByUser(User user, Pageable pageable);

    Page<Ticket> findByUserAndStatus(User user, TicketStatus status, Pageable pageable);

    @Query("SELECT t FROM Ticket t WHERE " +
           "(:search IS NULL OR LOWER(t.ticketNumber) LIKE LOWER(CONCAT('%',:search,'%')) OR " +
           "LOWER(t.subject) LIKE LOWER(CONCAT('%',:search,'%'))) " +
           "AND (:status IS NULL OR t.status = :status) " +
           "AND (:priority IS NULL OR t.priority = :priority) " +
           "AND (:category IS NULL OR t.category = :category) " +
           "AND (:userId IS NULL OR t.user.id = :userId)")
    Page<Ticket> filterTickets(@Param("search") String search,
                               @Param("status") TicketStatus status,
                               @Param("priority") TicketPriority priority,
                               @Param("category") TicketCategory category,
                               @Param("userId") Long userId,
                               Pageable pageable);

    @Query("SELECT t FROM Ticket t WHERE t.user = :user AND " +
           "(:search IS NULL OR LOWER(t.ticketNumber) LIKE LOWER(CONCAT('%',:search,'%')) OR " +
           "LOWER(t.subject) LIKE LOWER(CONCAT('%',:search,'%'))) " +
           "AND (:status IS NULL OR t.status = :status) " +
           "AND (:priority IS NULL OR t.priority = :priority) " +
           "AND (:category IS NULL OR t.category = :category)")
    Page<Ticket> filterUserTickets(@Param("user") User user,
                                   @Param("search") String search,
                                   @Param("status") TicketStatus status,
                                   @Param("priority") TicketPriority priority,
                                   @Param("category") TicketCategory category,
                                   Pageable pageable);

    long countByStatus(TicketStatus status);

    long countByPriority(TicketPriority priority);

    long countByCategory(TicketCategory category);

    long countByUser(User user);

    long countByUserAndStatus(User user, TicketStatus status);

    @Query("SELECT COUNT(t) FROM Ticket t WHERE t.createdAt >= :since")
    long countTicketsSince(@Param("since") LocalDateTime since);

    @Query("SELECT t.status as status, COUNT(t) as count FROM Ticket t GROUP BY t.status")
    List<Object[]> countByStatusGrouped();

    @Query("SELECT t.priority as priority, COUNT(t) as count FROM Ticket t GROUP BY t.priority")
    List<Object[]> countByPriorityGrouped();

    @Query("SELECT t.category as category, COUNT(t) as count FROM Ticket t GROUP BY t.category")
    List<Object[]> countByCategoryGrouped();

    @Query("SELECT DATE(t.createdAt) as date, COUNT(t) as count FROM Ticket t " +
           "WHERE t.createdAt >= :since GROUP BY DATE(t.createdAt) ORDER BY DATE(t.createdAt)")
    List<Object[]> countTicketsByDay(@Param("since") LocalDateTime since);

    @Query("SELECT AVG(TIMESTAMPDIFF(HOUR, t.createdAt, t.resolvedAt)) FROM Ticket t " +
           "WHERE t.status = 'RESOLVED' AND t.resolvedAt IS NOT NULL")
    Double getAverageResolutionTimeHours();
}

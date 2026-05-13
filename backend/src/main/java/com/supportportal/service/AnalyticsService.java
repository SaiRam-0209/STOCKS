package com.supportportal.service;

import com.supportportal.dto.response.AnalyticsResponse;
import com.supportportal.enums.*;
import com.supportportal.repository.AIResponseRepository;
import com.supportportal.repository.TicketRepository;
import com.supportportal.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;

@Service
@RequiredArgsConstructor
public class AnalyticsService {

    private final TicketRepository ticketRepository;
    private final UserRepository userRepository;
    private final AIResponseRepository aiResponseRepository;

    public AnalyticsResponse getAnalytics() {
        long totalTickets = ticketRepository.count();
        long openTickets = ticketRepository.countByStatus(TicketStatus.OPEN);
        long inProgressTickets = ticketRepository.countByStatus(TicketStatus.IN_PROGRESS);
        long resolvedTickets = ticketRepository.countByStatus(TicketStatus.RESOLVED);
        long closedTickets = ticketRepository.countByStatus(TicketStatus.CLOSED);
        long pendingTickets = ticketRepository.countByStatus(TicketStatus.PENDING);
        long totalUsers = userRepository.countByRole(UserRole.USER);
        long activeUsers = userRepository.countByIsActive(true);
        long newTicketsToday = ticketRepository.countTicketsSince(LocalDateTime.now().withHour(0).withMinute(0));
        long newTicketsThisWeek = ticketRepository.countTicketsSince(LocalDateTime.now().minusDays(7));
        long newTicketsThisMonth = ticketRepository.countTicketsSince(LocalDateTime.now().minusDays(30));
        Double avgResolutionTime = ticketRepository.getAverageResolutionTimeHours();
        long pendingAI = aiResponseRepository.countByStatus(AIResponseStatus.PENDING);
        long approvedAI = aiResponseRepository.countByStatus(AIResponseStatus.APPROVED);
        long rejectedAI = aiResponseRepository.countByStatus(AIResponseStatus.REJECTED);

        // Build maps for charts
        Map<String, Long> byStatus = new LinkedHashMap<>();
        byStatus.put("OPEN", openTickets);
        byStatus.put("IN_PROGRESS", inProgressTickets);
        byStatus.put("PENDING", pendingTickets);
        byStatus.put("RESOLVED", resolvedTickets);
        byStatus.put("CLOSED", closedTickets);

        Map<String, Long> byPriority = new LinkedHashMap<>();
        for (TicketPriority p : TicketPriority.values()) {
            byPriority.put(p.name(), ticketRepository.countByPriority(p));
        }

        Map<String, Long> byCategory = new LinkedHashMap<>();
        for (TicketCategory c : TicketCategory.values()) {
            byCategory.put(c.name(), ticketRepository.countByCategory(c));
        }

        // Trend for last 30 days
        List<Map<String, Object>> trend = new ArrayList<>();
        List<Object[]> trendData = ticketRepository.countTicketsByDay(LocalDateTime.now().minusDays(30));
        for (Object[] row : trendData) {
            Map<String, Object> point = new HashMap<>();
            point.put("date", row[0].toString());
            point.put("count", ((Number) row[1]).longValue());
            trend.add(point);
        }

        double resolutionRate = totalTickets > 0 ?
                (double)(resolvedTickets + closedTickets) / totalTickets * 100 : 0;
        long totalAI = approvedAI + rejectedAI;
        double aiApprovalRate = totalAI > 0 ? (double) approvedAI / totalAI * 100 : 0;

        return AnalyticsResponse.builder()
                .totalTickets(totalTickets)
                .openTickets(openTickets)
                .inProgressTickets(inProgressTickets)
                .resolvedTickets(resolvedTickets)
                .closedTickets(closedTickets)
                .pendingTickets(pendingTickets)
                .totalUsers(totalUsers)
                .activeUsers(activeUsers)
                .newTicketsToday(newTicketsToday)
                .newTicketsThisWeek(newTicketsThisWeek)
                .newTicketsThisMonth(newTicketsThisMonth)
                .averageResolutionTimeHours(avgResolutionTime)
                .pendingAIResponses(pendingAI)
                .approvedAIResponses(approvedAI)
                .rejectedAIResponses(rejectedAI)
                .ticketsByStatus(byStatus)
                .ticketsByPriority(byPriority)
                .ticketsByCategory(byCategory)
                .ticketsTrend(trend)
                .resolutionRate(resolutionRate)
                .aiApprovalRate(aiApprovalRate)
                .build();
    }
}

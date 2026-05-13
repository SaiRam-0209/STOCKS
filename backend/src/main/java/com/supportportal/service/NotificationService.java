package com.supportportal.service;

import com.supportportal.dto.response.NotificationResponse;
import com.supportportal.entity.Notification;
import com.supportportal.entity.Ticket;
import com.supportportal.entity.User;
import com.supportportal.enums.NotificationType;
import com.supportportal.enums.UserRole;
import com.supportportal.exception.ResourceNotFoundException;
import com.supportportal.repository.NotificationRepository;
import com.supportportal.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notificationRepository;
    private final UserRepository userRepository;

    @Transactional
    public void createNotification(User user, String title, String message,
                                   NotificationType type, Ticket ticket) {
        Notification notification = Notification.builder()
                .user(user)
                .title(title)
                .message(message)
                .type(type)
                .isRead(false)
                .ticket(ticket)
                .build();
        notificationRepository.save(notification);
    }

    @Transactional
    public void notifyAdmins(String title, String message, NotificationType type, Ticket ticket) {
        List<User> admins = userRepository.findByRole(UserRole.ADMIN,
                org.springframework.data.domain.Pageable.unpaged()).getContent();
        admins.forEach(admin -> createNotification(admin, title, message, type, ticket));
    }

    public Page<NotificationResponse> getUserNotifications(User user, Pageable pageable) {
        return notificationRepository.findByUserOrderByCreatedAtDesc(user, pageable)
                .map(this::mapToResponse);
    }

    public long getUnreadCount(User user) {
        return notificationRepository.countByUserAndIsRead(user, false);
    }

    @Transactional
    public void markAsRead(Long notificationId, User user) {
        Notification notification = notificationRepository.findById(notificationId)
                .orElseThrow(() -> new ResourceNotFoundException("Notification not found"));

        if (!notification.getUser().getId().equals(user.getId())) {
            throw new ResourceNotFoundException("Notification not found");
        }

        notification.setIsRead(true);
        notificationRepository.save(notification);
    }

    @Transactional
    public void markAllAsRead(User user) {
        notificationRepository.markAllAsReadForUser(user);
    }

    private NotificationResponse mapToResponse(Notification notification) {
        return NotificationResponse.builder()
                .id(notification.getId())
                .title(notification.getTitle())
                .message(notification.getMessage())
                .type(notification.getType())
                .isRead(notification.getIsRead())
                .ticketId(notification.getTicket() != null ? notification.getTicket().getId() : null)
                .ticketNumber(notification.getTicket() != null ? notification.getTicket().getTicketNumber() : null)
                .createdAt(notification.getCreatedAt())
                .build();
    }
}

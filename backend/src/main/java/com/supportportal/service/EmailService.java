package com.supportportal.service;

import com.supportportal.entity.Ticket;
import com.supportportal.entity.User;
import com.supportportal.enums.TicketStatus;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.thymeleaf.TemplateEngine;
import org.thymeleaf.context.Context;

@Service
@RequiredArgsConstructor
@Slf4j
public class EmailService {

    private final JavaMailSender mailSender;
    private final TemplateEngine templateEngine;

    @Value("${app.email.from}")
    private String fromEmail;

    @Value("${app.email.from-name}")
    private String fromName;

    @Value("${app.frontend.url}")
    private String frontendUrl;

    @Async
    public void sendWelcomeEmail(User user) {
        try {
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("userEmail", user.getEmail());
            context.setVariable("loginUrl", frontendUrl + "/auth/login");
            context.setVariable("portalName", "AI Support Portal");

            String html = templateEngine.process("email/welcome", context);
            sendEmail(user.getEmail(), "Welcome to AI Support Portal!", html);
        } catch (Exception e) {
            log.error("Failed to send welcome email to {}: {}", user.getEmail(), e.getMessage());
        }
    }

    @Async
    public void sendTicketCreatedEmail(User user, Ticket ticket) {
        try {
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("ticketNumber", ticket.getTicketNumber());
            context.setVariable("subject", ticket.getSubject());
            context.setVariable("category", ticket.getCategory().name());
            context.setVariable("priority", ticket.getPriority().name());
            context.setVariable("status", ticket.getStatus().name());
            context.setVariable("ticketUrl", frontendUrl + "/user/tickets/" + ticket.getId());
            context.setVariable("createdAt", ticket.getCreatedAt());

            String html = templateEngine.process("email/ticket-created", context);
            sendEmail(user.getEmail(), "Ticket Created: " + ticket.getTicketNumber(), html);
        } catch (Exception e) {
            log.error("Failed to send ticket created email: {}", e.getMessage());
        }
    }

    @Async
    public void sendTicketStatusUpdateEmail(User user, Ticket ticket, TicketStatus oldStatus) {
        try {
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("ticketNumber", ticket.getTicketNumber());
            context.setVariable("subject", ticket.getSubject());
            context.setVariable("oldStatus", oldStatus.name());
            context.setVariable("newStatus", ticket.getStatus().name());
            context.setVariable("ticketUrl", frontendUrl + "/user/tickets/" + ticket.getId());
            context.setVariable("updatedAt", ticket.getUpdatedAt());

            String html = templateEngine.process("email/ticket-status-update", context);
            sendEmail(user.getEmail(),
                    "Ticket " + ticket.getTicketNumber() + " Status Updated to " + ticket.getStatus(), html);
        } catch (Exception e) {
            log.error("Failed to send status update email: {}", e.getMessage());
        }
    }

    @Async
    public void sendTicketAssignedEmail(User user, Ticket ticket) {
        try {
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("ticketNumber", ticket.getTicketNumber());
            context.setVariable("subject", ticket.getSubject());
            context.setVariable("assignedTo", ticket.getAssignedTo() != null ? ticket.getAssignedTo().getName() : "AI Agent");
            context.setVariable("ticketUrl", frontendUrl + "/user/tickets/" + ticket.getId());

            String html = templateEngine.process("email/ticket-assigned", context);
            sendEmail(user.getEmail(), "Your Ticket " + ticket.getTicketNumber() + " Has Been Assigned", html);
        } catch (Exception e) {
            log.error("Failed to send ticket assigned email: {}", e.getMessage());
        }
    }

    @Async
    public void sendPasswordResetEmail(User user, String token) {
        try {
            String resetUrl = frontendUrl + "/auth/reset-password?token=" + token;
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("resetUrl", resetUrl);
            context.setVariable("expiryHours", 1);

            String html = templateEngine.process("email/password-reset", context);
            sendEmail(user.getEmail(), "Password Reset Request - AI Support Portal", html);
        } catch (Exception e) {
            log.error("Failed to send password reset email: {}", e.getMessage());
        }
    }

    @Async
    public void sendPasswordChangedConfirmation(User user) {
        try {
            Context context = new Context();
            context.setVariable("userName", user.getName());
            context.setVariable("loginUrl", frontendUrl + "/auth/login");

            String html = templateEngine.process("email/password-changed", context);
            sendEmail(user.getEmail(), "Password Changed Successfully - AI Support Portal", html);
        } catch (Exception e) {
            log.error("Failed to send password changed email: {}", e.getMessage());
        }
    }

    private void sendEmail(String to, String subject, String html) throws MessagingException {
        MimeMessage mimeMessage = mailSender.createMimeMessage();
        MimeMessageHelper helper = new MimeMessageHelper(mimeMessage, true, "UTF-8");
        helper.setFrom(fromEmail, fromName);
        helper.setTo(to);
        helper.setSubject(subject);
        helper.setText(html, true);
        mailSender.send(mimeMessage);
        log.info("Email sent to {} with subject: {}", to, subject);
    }
}

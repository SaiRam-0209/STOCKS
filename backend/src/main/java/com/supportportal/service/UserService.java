package com.supportportal.service;

import com.supportportal.dto.request.PasswordChangeRequest;
import com.supportportal.dto.request.UserUpdateRequest;
import com.supportportal.dto.response.UserResponse;
import com.supportportal.entity.User;
import com.supportportal.enums.TicketStatus;
import com.supportportal.enums.UserRole;
import com.supportportal.exception.BadRequestException;
import com.supportportal.exception.DuplicateResourceException;
import com.supportportal.exception.ResourceNotFoundException;
import com.supportportal.repository.TicketRepository;
import com.supportportal.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final TicketRepository ticketRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuditLogService auditLogService;
    private final NotificationService notificationService;

    public UserResponse getUserById(Long id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User not found with id: " + id));
        return mapToResponse(user);
    }

    public UserResponse getCurrentUserProfile(User currentUser) {
        return mapToResponse(currentUser);
    }

    @Transactional
    public UserResponse updateProfile(User currentUser, UserUpdateRequest request) {
        currentUser.setName(request.getName().trim());
        currentUser.setPhone(request.getPhone());
        currentUser.setDepartment(request.getDepartment());
        userRepository.save(currentUser);
        auditLogService.log(currentUser, "PROFILE_UPDATED", "User", currentUser.getId(), "Profile updated", null);
        return mapToResponse(currentUser);
    }

    @Transactional
    public void changePassword(User currentUser, PasswordChangeRequest request) {
        if (!passwordEncoder.matches(request.getCurrentPassword(), currentUser.getPassword())) {
            throw new BadRequestException("Current password is incorrect. Please try again.");
        }

        if (!request.getNewPassword().equals(request.getConfirmPassword())) {
            throw new BadRequestException("New passwords do not match. Please try again.");
        }

        if (passwordEncoder.matches(request.getNewPassword(), currentUser.getPassword())) {
            throw new BadRequestException("New password cannot be the same as the current password.");
        }

        currentUser.setPassword(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(currentUser);
        auditLogService.log(currentUser, "PASSWORD_CHANGED", "User", currentUser.getId(), "Password changed", null);
    }

    // Admin operations
    public Page<UserResponse> getAllUsers(String search, UserRole role, Boolean isActive, Pageable pageable) {
        return userRepository.searchUsers(search, role, isActive, pageable)
                .map(this::mapToResponse);
    }

    @Transactional
    public UserResponse createUser(com.supportportal.dto.request.RegisterRequest request, User admin) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new DuplicateResourceException("An account with this email already exists.");
        }

        User user = User.builder()
                .name(request.getName().trim())
                .email(request.getEmail().toLowerCase().trim())
                .password(passwordEncoder.encode(request.getPassword()))
                .role(UserRole.USER)
                .phone(request.getPhone())
                .department(request.getDepartment())
                .isActive(true)
                .build();

        userRepository.save(user);
        auditLogService.log(admin, "USER_CREATED", "User", user.getId(), "Admin created user: " + user.getEmail(), null);
        return mapToResponse(user);
    }

    @Transactional
    public UserResponse toggleUserStatus(Long userId, User admin) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User not found with id: " + userId));

        if (user.getRole() == UserRole.ADMIN) {
            throw new BadRequestException("Cannot deactivate an admin account.");
        }

        user.setIsActive(!user.getIsActive());
        userRepository.save(user);
        String action = user.getIsActive() ? "USER_ACTIVATED" : "USER_DEACTIVATED";
        auditLogService.log(admin, action, "User", user.getId(),
                "Admin " + action.toLowerCase() + " user: " + user.getEmail(), null);
        return mapToResponse(user);
    }

    @Transactional
    public void deleteUser(Long userId, User admin) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User not found with id: " + userId));

        if (user.getRole() == UserRole.ADMIN) {
            throw new BadRequestException("Cannot delete an admin account.");
        }

        auditLogService.log(admin, "USER_DELETED", "User", user.getId(),
                "Admin deleted user: " + user.getEmail(), null);
        userRepository.delete(user);
    }

    public UserResponse mapToResponse(User user) {
        long totalTickets = ticketRepository.countByUser(user);
        long openTickets = ticketRepository.countByUserAndStatus(user, TicketStatus.OPEN);
        long resolvedTickets = ticketRepository.countByUserAndStatus(user, TicketStatus.RESOLVED);

        return UserResponse.builder()
                .id(user.getId())
                .name(user.getName())
                .email(user.getEmail())
                .role(user.getRole())
                .phone(user.getPhone())
                .department(user.getDepartment())
                .profilePicture(user.getProfilePicture())
                .isActive(user.getIsActive())
                .lastLogin(user.getLastLogin())
                .createdAt(user.getCreatedAt())
                .totalTickets(totalTickets)
                .openTickets(openTickets)
                .resolvedTickets(resolvedTickets)
                .build();
    }
}

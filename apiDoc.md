
## FinSyncOrganizations API Documentation

### 1. Organizations

#### 1.1 Create New Organization
*   **Endpoint:** `POST /api/organizations/`
*   **Description:** Allows an authenticated user to create a new organization. The user who creates the organization becomes its initial owner and a member. They are automatically moved from their previous organization (if any) to this newly created one. The new organization is set up with a default trial subscription plan.
*   **Permissions:** `IsAuthenticated`
*   **Request Body:** (`application/json`)
    ```json
    {
        "name": "string (required)"
    }
    ```
    *   `name`: The desired name for the new organization.
*   **Responses:**
    *   `201 Created`: Organization created successfully.
        ```json
        {
            "name": "string" // Name of the created organization
            // Other organization fields might be included depending on serializer depth
        }
        ```
    *   `400 Bad Request`: Invalid input (e.g., name missing or invalid).
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `500 Internal Server Error`: If organization creation fails for an unexpected reason (e.g. database issue during transaction).
*   **Key Actions:**
    *   Creates a new `Organization` record.
    *   Sets the requesting user as `created_by` and `owner`.
    *   Applies a default trial plan to the new organization.
    *   If the user was part of another organization, logs their departure (`LEFT_ORG`).
    *   Moves the user to the newly created organization.
    *   Logs the user joining the new organization (`JOINED_ORG_VIA_SIGNUP` or similar).

---

### 2. Organization Invites

#### 2.1 List Organization Invites
*   **Endpoint:** `GET /api/organizations/{organization_id}/invites/`
*   **Description:** Retrieves a list of pending and past invitations for a specific organization.
*   **Permissions:** `IsAuthenticated`, `IsOrganizationMember` (User must be a member of the specified `organization_id`).
*   **Path Parameters:**
    *   `organization_id` (integer): The ID of the organization whose invites are to be listed.
*   **Responses:**
    *   `200 OK`:
        ```json
        [
            {
                "id": "uuid",
                "organization": "integer", // ID of the organization
                "organization_name": "string",
                "code": "string", // Invite code
                "email": "string (nullable)", // Email address the invite was sent to, if any
                "created_by": "integer", // ID of the user who created the invite
                "created_by_email": "string",
                "is_active": "boolean", // Whether the invite can still be used
                "created_at": "datetime",
                "expires_at": "datetime (nullable)" // When the invite expires
            }
            // ... more invites
        ]
        ```
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: User is not a member of the organization.
    *   `404 Not Found`: Organization not found.

#### 2.2 Create Organization Invite
*   **Endpoint:** `POST /api/organizations/{organization_id}/invites/`
*   **Description:** Creates a new invitation for a user to join a specific organization.
*   **Permissions:** `IsAuthenticated`, `IsOrganizationMember` (User must be a member of the specified `organization_id` to send invites).
*   **Path Parameters:**
    *   `organization_id` (integer): The ID of the organization to invite someone to.
*   **Request Body:** (`application/json`)
    ```json
    {
        "email": "string (optional)", // Email address to send the invite to (can be specific)
        "expires_at": "datetime (optional)" // ISO 8601 format. If not provided, a default expiry is set.
    }
    ```
*   **Responses:**
    *   `201 Created`: Invite created successfully. Response body will contain the details of the created invite (similar to the GET list response for a single invite).
    *   `400 Bad Request`: Invalid input (e.g., invalid email format, expiration date in the past).
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: User is not a member of the organization.
    *   `404 Not Found`: Organization not found.
*   **Key Actions:**
    *   Creates an `OrganizationInvite` record.
    *   The requesting user is set as `created_by`.
    *   The system checks if the organization `can_add_user()` based on its plan (currently this is a soft check and doesn't prevent invite creation).

#### 2.3 Accept Organization Invite
*   **Endpoint:** `POST /api/invites/accept/`
*   **Description:** Allows an authenticated user to accept an organization invitation using an invite code. If successful, the user is moved to the invited organization.
*   **Permissions:** `IsAuthenticated`
*   **Request Body:** (`application/json`)
    ```json
    {
        "code": "string (required)" // The invite code
    }
    ```
*   **Responses:**
    *   `200 OK`: Invite accepted successfully.
        ```json
        {
            "detail": "Successfully joined organization: {organization_name}"
        }
        ```
    *   `400 Bad Request`: Invalid input (e.g., code missing, invite expired, invite for different email, organization at user limit).
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: Invite is intended for a different email address.
    *   `404 Not Found`: Invite code not found or invalid.
*   **Key Actions:**
    *   Validates the invite code (active, not expired, matches user's email if specified).
    *   Checks if the target organization is active and `can_add_user()`.
    *   Moves the user to the target organization by updating their `organization` field.
    *   Marks the `OrganizationInvite` as used.
    *   Logs the event to application logs (Note: Does not currently create an `OrganizationMembershipLog` record for this action).

---

### 3. Organization Membership Management

#### 3.1 Leave Current Organization
*   **Endpoint:** `POST /api/organizations/leave/`
*   **Description:** Allows an authenticated user to leave their current organization. Upon leaving, a new personal organization (e.g., "{user.email}'s Workspace") is automatically created for the user, and they are moved into it.
*   **Permissions:** `IsAuthenticated`
*   **Request Body:** None
*   **Responses:**
    *   `200 OK`: Successfully left organization and moved to a new personal workspace.
        ```json
        {
            "detail": "You have left '{current_organization.name}' and are now in your new personal workspace: '{personal_org.name}'."
        }
        ```
    *   `400 Bad Request`: User is not part of any organization.
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: Superuser attempting to leave a designated admin organization.
    *   `500 Internal Server Error`: If creation of the personal workspace fails.
*   **Key Actions:**
    *   Identifies the user's current organization.
    *   Creates a new personal `Organization` for the user (setting user as `created_by` and `owner`, applies trial plan).
    *   Logs the user leaving the current organization (`LEFT_ORG`).
    *   Updates the user's `organization` field to the new personal organization.
    *   Logs the user joining the new personal organization (`JOINED_ORG_VIA_SIGNUP` or similar).

#### 3.2 Change Organization Owner
*   **Endpoint:** `POST /api/organizations/{organization_id}/change-owner/`
*   **Description:** Allows the current owner of an organization to transfer ownership to another active member of the same organization.
*   **Permissions:** `IsAuthenticated`, `IsOrganizationOwner` (Requesting user must be the current owner of the `organization_id`).
*   **Path Parameters:**
    *   `organization_id` (integer): The ID of the organization whose owner is to be changed.
*   **Request Body:** (`application/json`)
    ```json
    {
        "new_owner_email": "string (required)" // Email of the user to become the new owner
    }
    ```
*   **Responses:**
    *   `200 OK`: Ownership transferred successfully.
        ```json
        {
            "detail": "Ownership of '{organization.name}' transferred to {new_owner.email}."
        }
        ```
    *   `400 Bad Request`: Invalid input (e.g., new owner email does not exist, new owner is not part of the organization, new owner is already the owner).
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: Requesting user is not the owner of the organization.
    *   `404 Not Found`: Organization or specified new owner user not found.
*   **Key Actions:**
    *   Validates that `new_owner_email` corresponds to an active user who is a member of the organization.
    *   Updates the `owner` field of the `Organization`.
    *   Logs the ownership change to application logs (Note: Does not currently create an `OrganizationMembershipLog` record for this action).

#### 3.3 Remove Member from Organization (Admin Action)
*   **Endpoint:** `POST /api/organizations/{organization_id}/members/{user_id_to_remove}/remove/`
*   **Description:** Allows an organization owner to remove a member from their organization. The removed member is automatically moved to a new personal organization created for them.
*   **Permissions:** `IsAuthenticated`, `IsOrganizationOwner` (Requesting user must be the owner of `organization_id`).
*   **Path Parameters:**
    *   `organization_id` (integer): The ID of the organization.
    *   `user_id_to_remove` (integer): The ID of the user to be removed from the organization.
*   **Request Body:** None
*   **Responses:**
    *   `200 OK`: User removed successfully.
        ```json
        {
            "detail": "User '{user_to_remove.email}' has been removed from '{organization.name}' and moved to a new personal workspace."
        }
        ```
    *   `400 Bad Request`: Invalid action (e.g., owner trying to remove themselves, user is not a member of the organization).
    *   `401 Unauthorized`: Authentication credentials were not provided.
    *   `403 Forbidden`: Requesting user is not the owner of the organization.
    *   `404 Not Found`: Organization or user_to_remove not found.
    *   `500 Internal Server Error`: If creation of the personal workspace for the removed user fails.
*   **Key Actions:**
    *   Verifies requesting user is the owner and not trying to remove themselves.
    *   Creates a new personal `Organization` for the `user_to_remove` (setting them as `created_by` and `owner`, applies trial plan).
    *   Logs the removal from the current organization (`REMOVED_BY_ADMIN`).
    *   Updates the removed user's `organization` field to their new personal organization.
    *   Logs the removed user joining their new personal organization (`JOINED_ORG_VIA_SIGNUP` or similar).

---

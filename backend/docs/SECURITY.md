# Security Implementation

## Authentication
- JWT tokens with configurable expiry
- Tokens stored in localStorage (CSRF-safe)
- Password hashing with bcrypt
- Google OAuth available via Authorization Code flow

## Rate Limiting
- 60 requests/minute for general endpoints
- 5 requests/minute for auth endpoints
- IP-based limiting via Redis
- Fails open if Redis unavailable (requests are allowed to proceed)

## Password Requirements
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character
- Common passwords rejected

## Input Validation
- All inputs sanitized for XSS (HTML encoding)
- Email format validation
- Username: 3-50 characters, alphanumeric and underscores only
- String inputs truncated to prevent overflow

## OAuth
- Google OAuth via Authorization Code flow
- Backend exchanges code for tokens
- Existing accounts can be linked
- OAuth users have empty password hash

## Session Management
- Track active sessions in database
- Token hash stored (not raw token)
- View all active sessions
- Revoke individual sessions
- Logout all devices option

## CSRF Protection
- JWT tokens in Authorization header (not cookies) provide inherent CSRF protection
- Attackers cannot read localStorage cross-origin to steal tokens
- Cross-site requests cannot include the Authorization header with the JWT
- SessionMiddleware used for OAuth state management (not CSRF)

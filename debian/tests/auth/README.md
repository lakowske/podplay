# Authentication Testing

Simple authentication testing for PodPlay.

## Current Status

The authentication system is working but has these limitations during testing:

1. **Email Sending**: The mail server is not configured to send emails during testing, so registration and password reset emails fail to send. However, the tokens are still created in the filesystem.

2. **Login Issues**: There appears to be a mismatch between how passwords are hashed during registration vs login verification. This may be due to the user management system expecting a different format.

## Test Structure

- `simple_auth_test.py` - Main test script with 3 core workflows
- `auth_client.py` - Simple HTTP client for authentication endpoints  
- `test_config.py` - Basic configuration

## Running Tests

```bash
cd debian
make test-auth
```

## Future Improvements

1. Configure test email sending or mock SMTP
2. Debug password hashing/verification mismatch
3. Add more detailed error reporting
4. Test with actual working credentials
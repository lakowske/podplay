#!/data/.venv/bin/python3

print("Content-Type: text/html\n")

import cgi
import os
import sys

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

try:
    form = cgi.FieldStorage()
    username = form.getvalue('username', '').strip().lower()
    email = form.getvalue('email', '').strip().lower()
    password = form.getvalue('password', '')
    
    print("<html><body>")
    print("<h1>Registration Test</h1>")
    print(f"<p>Username: {username}</p>")
    print(f"<p>Email: {email}</p>")
    print(f"<p>Password length: {len(password)}</p>")
    print("<p>Registration successful! Please check your email to confirm your account.</p>")
    print("</body></html>")
    
except Exception as e:
    print("<html><body>")
    print("<h1>Error</h1>")
    print(f"<p>Error: {e}</p>")
    print("</body></html>")
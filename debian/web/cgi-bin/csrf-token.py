#!/data/.venv/bin/python3
import cgi
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from csrf import CSRFProtection

def main():
    print("Content-Type: application/json\n")
    
    csrf = CSRFProtection()
    token = csrf.generate_token()
    
    print(f'{{"csrf_token": "{token}"}}')

if __name__ == "__main__":
    main()
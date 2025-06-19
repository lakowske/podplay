#!/usr/bin/env python3
"""
Test DNS server functionality
"""

import subprocess
import socket
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

# Configuration
DNS_SERVER = "127.0.0.1"
DNS_PORT = 8053
DOMAIN = "lab.sethlakowske.com"

def print_success(msg):
    print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

def print_error(msg):
    print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

def print_info(msg):
    print(f"{Fore.BLUE}ℹ {msg}{Style.RESET_ALL}")

def test_dns_query(record_type, query, expected_response=None):
    """Test a DNS query using dig"""
    try:
        cmd = ["dig", f"@{DNS_SERVER}", "-p", str(DNS_PORT), "+short", record_type, query]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            response = result.stdout.strip()
            if response:
                print_success(f"{record_type} query for {query}: {response}")
                if expected_response and expected_response in response:
                    print_success(f"Expected response found: {expected_response}")
                return True
            else:
                print_error(f"{record_type} query for {query}: No response")
                return False
        else:
            print_error(f"{record_type} query failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error(f"{record_type} query timed out")
        return False
    except Exception as e:
        print_error(f"{record_type} query error: {e}")
        return False

def test_dns_connectivity():
    """Test basic DNS server connectivity"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.connect((DNS_SERVER, DNS_PORT))
        print_success(f"DNS server is reachable at {DNS_SERVER}:{DNS_PORT}")
        sock.close()
        return True
    except Exception as e:
        print_error(f"Cannot connect to DNS server: {e}")
        return False

def main():
    print(f"{Fore.CYAN}=== DNS Server Test ==={Style.RESET_ALL}")
    print(f"Testing DNS server at {DNS_SERVER}:{DNS_PORT}")
    print(f"Domain: {DOMAIN}\n")
    
    # Test connectivity
    if not test_dns_connectivity():
        print_error("DNS server is not reachable. Aborting tests.")
        return 1
    
    print(f"\n{Fore.YELLOW}Testing DNS Records:{Style.RESET_ALL}")
    
    # Test A records
    test_dns_query("A", DOMAIN, "192.168.1.100")
    test_dns_query("A", f"www.{DOMAIN}", "192.168.1.100")
    test_dns_query("A", f"mail.{DOMAIN}", "192.168.1.100")
    test_dns_query("A", f"ns1.{DOMAIN}", "192.168.1.100")
    test_dns_query("A", f"ns2.{DOMAIN}", "192.168.1.100")
    
    # Test MX record
    print(f"\n{Fore.YELLOW}Testing Mail Records:{Style.RESET_ALL}")
    test_dns_query("MX", DOMAIN, f"mail.{DOMAIN}")
    
    # Test NS records
    print(f"\n{Fore.YELLOW}Testing Name Server Records:{Style.RESET_ALL}")
    test_dns_query("NS", DOMAIN, f"ns1.{DOMAIN}")
    
    # Test SOA record
    print(f"\n{Fore.YELLOW}Testing SOA Record:{Style.RESET_ALL}")
    test_dns_query("SOA", DOMAIN)
    
    # Test TXT records
    print(f"\n{Fore.YELLOW}Testing TXT Records:{Style.RESET_ALL}")
    test_dns_query("TXT", DOMAIN, "v=spf1")
    test_dns_query("TXT", f"_dmarc.{DOMAIN}", "v=DMARC1")
    
    # Test CNAME records
    print(f"\n{Fore.YELLOW}Testing CNAME Records:{Style.RESET_ALL}")
    test_dns_query("CNAME", f"webmail.{DOMAIN}", f"mail.{DOMAIN}")
    test_dns_query("CNAME", f"imap.{DOMAIN}", f"mail.{DOMAIN}")
    test_dns_query("CNAME", f"smtp.{DOMAIN}", f"mail.{DOMAIN}")
    
    # Test reverse DNS
    print(f"\n{Fore.YELLOW}Testing Reverse DNS:{Style.RESET_ALL}")
    test_dns_query("PTR", "1.10.in-addr.arpa", DOMAIN)
    
    # Test external domain resolution (forwarding)
    print(f"\n{Fore.YELLOW}Testing DNS Forwarding:{Style.RESET_ALL}")
    test_dns_query("A", "google.com")
    test_dns_query("A", "cloudflare.com")
    
    print(f"\n{Fore.GREEN}DNS server tests completed!{Style.RESET_ALL}")
    return 0

if __name__ == "__main__":
    exit(main())
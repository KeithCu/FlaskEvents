#!/usr/bin/env python3
"""Generate a werkzeug password hash for config.yaml admin.password_hash."""
import sys

from werkzeug.security import generate_password_hash


def main():
    if len(sys.argv) != 2:
        print("Usage: python hash_password.py 'your-plaintext-password'", file=sys.stderr)
        sys.exit(1)
    print(generate_password_hash(sys.argv[1]))


if __name__ == '__main__':
    main()

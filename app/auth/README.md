# auth

- `ssh_auth.py`: Uses SSH key authentication via a challenge/response mechanism.

Example:
1) Challenge sends cryptographically secure challenge to user
2) Challenge is signed using the admin key (to gain access, similarly to SSH Key Authentication via OpenSSH)
---
title: 'X.509 Certificates Explained: Uses, Fields, Certificate Authoritiess, and Certificate Transparency'
summary: 'A concise field guide to X.509 certificates: what they’re used for, how
  to read their fields in a browser, and where Certificate Authorities and Certificate
  Transparency fit.'
tags:
- x509
- tls
- ssl
- PKI
published: true
date: '2025-12-31'
slug: x509-certificates-explained-uses-fields-cas-transparency
---

X.509 is the standard format for public key certificates. This post distills the essentials: the common uses of X.509 certificates, the core fields you’ll see when you inspect one in your browser, and how Certificate Authorities and Certificate Transparency fit into the ecosystem. The goal is to make the terminology and structure concrete so you can quickly orient yourself when reviewing a cert or validating trust decisions.

## Table of Contents
- [What is an X.509 Certificate Used For?](#what-is-an-x509-certificate-used-for)
- [Inside an X.509 Certificate](#inside-an-x509-certificate)
- [Certificate Authority](#certificate-authority)

## What is an X.509 Certificate Used For?
- Email Security
- Online Document Signature's
- TLS (Transport Layer Security)
- SSL (Secure Sockets Layer)

Standard format for public key certificates.

- Different versions
- Not all certificates require public trust

Each **Certificate** includes:
- Public Key
- Digital Signature
- Issuing CA
- Additional Information About the certificate

These use cases and properties set the stage for what you’ll see when you inspect a certificate. The next section walks through the fields exposed by typical browser tooling.

## Inside an X.509 Certificate
Click the (lock) icon in your browser, click on the Certificate > Details

- **Version:** The iteration of the X.509 certificate being issued to a user.
- **Serial Number:** A unique number assigned to each X.509 certificate by the CA.
- **Signature Algorithm ID:** The specific mathematical algorithm used to create and encrypt the CA’s private key.
- **Issuer:** The name of the CA who issued the X.509 certificate.
- **Validity Period:** The timeframe in which the X.509 certificate can be used before it expires and becomes obsolete. It includes the start and end dates that the certificate is viable.
- **Subject:** The user’s name or the type of device that receives the X.509 certificate from the CA.
- **Subject Public Key Information:** This includes the algorithm used to generate the public key attached to the X.509 certificate, the public key itself, and additional data such as the key’s size and unique function.
- **Certificate Signature Algorithm:** The type of algorithm involved in signing and encrypting the X.509 certificate.
- **Certificate Signature:** A long, alphanumerical string unique to the identity of the CA issuing the X.509 certificate.

These fields collectively describe the certificate’s identity, scope, and cryptographic underpinnings. Together, they provide the data points you need to evaluate who the certificate belongs to, who issued it, what time window it is valid for, and the algorithms involved in its creation and verification.

## Certificate Authority
Company or organization that acts to validate the identities of entities and bind them to cryptographic keys through the issuance of digital certificates.

[Source](https://courses.cs.washington.edu/courses/cse484/21wi/sections/slides/section_05.pdf)

![Certificate](/static/img/20231220055333.png)

#### Certificate Transparency

Certificate Transparency monitoring & audits. It can be used from the command line as follows:
**Certificate Transparency (CT)** is a public, append-only logging system for TLS certificates. Its entire purpose is to make certificate issuance **auditable** so that mis-issuance can’t happen quietly.

In other words:  
CT makes certificates _observable_, not _trustworthy_. Trust still comes from CAs. Transparency comes from logs.

### Why CT exists

Before CT:

- A compromised or malicious Certificate Authority could issue a valid TLS certificate for **any domain**
- The site owner might **never know**
- Browsers would accept it silently
    

After several high-profile CA compromises, CT was introduced to make **every publicly trusted certificate visible to everyone**.

Modern browsers now **require** CT logging for publicly trusted certificates.

---

## crt.sh: A Public CT Log Search Engine

**crt.sh** is a search interface that aggregates Certificate Transparency logs and allows you to query them by:

- Domain   
- Organization
- Certificate fingerprint
- Serial number
- Email
- Wildcards

```bash
curl "https://crt.sh/?q=example.com&output=json" -H "Content-Type: application/json" | jq
[SNIP]...
```

**Output**
```bash
[
  {
    "issuer_ca_id": 204407,
    "issuer_name": "C=GB, O=Sectigo Limited, CN=Sectigo Public Server Authentication CA DV E36",
    "common_name": "example.com",
    "name_value": "*.example.com\nexample.com",
    "id": 23164227397,
    "entry_timestamp": "2025-12-16T21:50:43.225",
    "not_before": "2025-12-16T00:00:00",
    "not_after": "2026-03-16T20:59:52",
    "serial_number": "4b87ab08fde761c73d3c9f7a6a141bd3",
    "result_count": 3
  },
  {
    "issuer_ca_id": 204407,
    "issuer_name": "C=GB, O=Sectigo Limited, CN=Sectigo Public Server Authentication CA DV E36",
    "common_name": "example.com",
    "name_value": "*.example.com\nexample.com",
    "id": 23164227256,
    "entry_timestamp": "2025-12-16T21:50:41.574",
    "not_before": "2025-12-16T00:00:00",
    "not_after": "2026-03-16T20:59:52",
    "serial_number": "4b87ab08fde761c73d3c9f7a6a141bd3",
    "result_count": 3
  },
  {
    "issuer_ca_id": 204406,
    "issuer_name": "C=GB, O=Sectigo Limited, CN=Sectigo Public Server Authentication CA DV R36",
    "common_name": "example.com",
    "name_value": "*.example.com\nexample.com",
    "id": 23163376071,
    "entry_timestamp": "2025-12-16T20:59:37.431",
    "not_before": "2025-12-16T00:00:00",
    "not_after": "2026-03-16T16:12:36",
    "serial_number": "7492bfdffaa42846b8a14370d3d8b3f5",
    "result_count": 3
  },
  {
    "issuer_ca_id": 204406,
    "issuer_name": "C=GB, O=Sectigo Limited, CN=Sectigo Public Server Authentication CA DV R36",
    "common_name": "example.com",
    "name_value": "*.example.com\nexample.com",
    "id": 23163377090,
    "entry_timestamp": "2025-12-16T20:59:36.318",
    "not_before": "2025-12-16T00:00:00",
    "not_after": "2026-03-16T16:12:36",
    "serial_number": "7492bfdffaa42846b8a14370d3d8b3f5",
    "result_count": 3
  },
  {
    "issuer_ca_id": 413868,
    "issuer_name": "C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3",
    "common_name": "example.com",
    "name_value": "*.example.com\nexample.com",
    "id": 23162254871,
    "entry_timestamp": "2025-12-16T19:49:36.444",
    "not_before": "2025-12-16T19:39:32",
    "not_after": "2026-03-16T18:32:44",
    "serial_number": "1ede98307ea0594823ea81baf6154a67",
    "result_count": 3
  },
.... [SNIP]
```




---

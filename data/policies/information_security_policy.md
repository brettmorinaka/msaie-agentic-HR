# GlobalTech Information Security & Data Governance Policy

**Document ID:** POL-SEC-2024  
**Effective Date:** January 1, 2024  
**Last Revised:** April 10, 2024  
**Category:** Information Security & Data Privacy  
**Audience:** All GlobalTech Employees, Contractors, and Third-Party System Users  
**Policy Owner:** Office of the Chief Information Security Officer (CISO) & Data Privacy Officer  

---

## 1. Purpose and Information Security Architecture
In an era of sophisticated cybersecurity threats, cloud-native software architectures, and global regulatory compliance frameworks (including SOC 2 Type II, ISO/IEC 27001, HIPAA, and the European Union General Data Protection Regulation [GDPR]), safeguarding the confidentiality, integrity, and availability of GlobalTech information assets is paramount.

This policy establishes the mandatory standards, technical controls, data handling protocols, authentication requirements, and security practices governing all computational devices, cloud infrastructure, network communications, enterprise data stores, and personnel. Compliance with this policy is a non-negotiable condition of employment.

---

## 2. Enterprise Data Classification Hierarchy
All information created, stored, processed, or transmitted within GlobalTech systems is categorized into one of four distinct classification tiers, each requiring specific protective controls:

### 2.1 Tier 1: Public Information
- **Definition:** Information explicitly approved by Corporate Communications and Legal for unrestricted public dissemination.
- **Examples:** Published marketing brochures, public documentation sites, open-source repositories (MIT/Apache 2.0 licensed), published press releases, and approved job postings.
- **Handling Controls:** No encryption required for storage. Integrity must be maintained via digital signatures on official software releases.

### 2.2 Tier 2: Internal Information
- **Definition:** Information intended solely for internal operational consumption by GlobalTech personnel. Unauthorized disclosure would cause minor administrative inconvenience but no financial or reputational harm.
- **Examples:** Internal organizational charts, general Slack channel discussions, company all-hands slide decks, internal wiki architecture pages, and facilities schedules.
- **Handling Controls:** Accessible to all authenticated employees. Storage permitted on approved corporate cloud drives (Google Drive, Notion, GitHub Enterprise). Forwarding to external personal email accounts is prohibited.

### 2.3 Tier 3: Confidential Information
- **Definition:** Sensitive business information whose unauthorized disclosure could result in financial loss, competitive disadvantage, contractual breach, or moderate regulatory sanctions.
- **Examples:** Proprietary software algorithms, unreleased product roadmap features, pre-announcement financial performance metrics, commercial vendor contracts, employee compensation structures, and strategic business development plans.
- **Handling Controls:** Access governed by the Principle of Least Privilege. Must be encrypted in transit (TLS 1.3) and at rest (AES-256). Sharing restricted to employees with a verified business need-to-know.

### 2.4 Tier 4: Restricted / Highly Sensitive Information
- **Definition:** Highly regulated, critical data whose compromise would result in severe financial penalties, catastrophic brand harm, criminal liability, or major regulatory enforcement.
- **Examples:** Customer Personally Identifiable Information (PII) including Social Security Numbers, government tax IDs, bank account details; customer production database snapshots; customer encryption keys (KMS); and production cloud infrastructure root credentials.
- **Handling Controls:** Strict role-based access control (RBAC) with Multi-Party Approval (MPA) and Just-In-Time (JIT) access grants limited to four (4) hours maximum. Stored exclusively in segregated, air-gapped or audited cloud vaults. Zero customer production data may ever be downloaded to local developer workstations, laptops, or external portable media.

---

## 3. Identity, Authentication, and Access Management

### 3.1 Passphrase & Authentication Complexity
- **Passphrase Length:** Where password authentication is required, passphrases must contain a minimum of **sixteen (16) characters**. Passphrases must incorporate a combination of uppercase letters, lowercase letters, numbers, and special symbols.
- **Prohibited Passwords:** Dictionary words, sequential strings (e.g., "123456"), company names, or previously breached credentials detected by our automated credential monitoring systems will be rejected.
- **Enterprise Password Managers:** Employees are provisioned enterprise 1Password accounts. Storing corporate credentials in web browser caches, plaintext sticky notes, or unencrypted text files is strictly forbidden.

### 3.2 Mandatory Multi-Factor Authentication (MFA / 2FA)
- Multi-Factor Authentication is universally enforced across all single sign-on (Okta) enterprise applications, cloud infrastructure providers (AWS, GCP), GitHub Enterprise, and corporate email accounts.
- **Hardware Security Keys:** Engineering, DevOps, IT, and Finance team members must utilize FIDO2/WebAuthn hardware security keys (**YubiKey 5-series**) as their primary authentication factor.
- **Prohibited MFA Methods:** SMS-based text message verification and voice call verification are deemed vulnerable to SIM-swapping attacks and are prohibited for all internal corporate accounts.

### 3.3 Principle of Least Privilege & Quarterly Access Audits
- Access to production databases, cloud management consoles, and sensitive repositories is granted on the Principle of Least Privilege: users are provisioned only the minimum permissions necessary to complete their job responsibilities.
- All elevated administrative permissions undergo automated **quarterly access certification reviews** conducted by IT Security and Department Leads. Inactive or stale accounts are automatically deprovisioned after thirty (30) days of non-use.

---

## 4. Workstation Security and Device Encryption

### 4.1 Full-Disk Encryption & Mobile Device Management (MDM)
- Every computer connecting to the GlobalTech network must be an enterprise-managed asset enrolled in our centralized MDM platform (Jamf Pro for macOS; Microsoft Intune for Windows).
- **Mandatory Encryption:** Full-disk encryption (**FileVault 2** on macOS with XTS-AES-128; **BitLocker** with TPM 2.0 on Windows; **LUKS** on Linux) must be active at all times. Recovery keys are escrowed in encrypted enterprise key stores.
- Disabling MDM agents, altering endpoint detection and response (EDR) sensors (CrowdStrike Falcon), or jailbreaking/rooting corporate devices will result in immediate network quarantine.

### 4.2 Automated Screen Locking & Clean Desk Standards
- All corporate computers are configured to lock displays automatically after **five (5) minutes of user inactivity**.
- Employees must manually lock screens whenever stepping away from their physical workstation (`Cmd + Ctrl + Q` on macOS; `Windows Key + L` on Windows).
- In corporate offices and co-working spaces, employees must maintain a Clean Desk: sensitive documents, access badges, and YubiKeys must never be left unattended on desks overnight.

---

## 5. Acceptable Use of Artificial Intelligence (AI) and Large Language Models (LLMs)

GlobalTech champions the innovative use of artificial intelligence to augment engineering velocity and operational productivity; however, proprietary intellectual property and customer trust must be rigorously preserved:

### 5.1 Approved Enterprise AI Gateways
- Employees may utilize AI models (including GPT-4, Claude 3.5, Gemini, and open-source models) exclusively through our approved **GlobalTech Enterprise AI Gateway** or designated enterprise workspace subscriptions that provide contractual guarantees of zero data training, enterprise encryption, and data segregation.

### 5.2 Strict Prohibition on Customer Data in Public AI Models
- **Customer PII & Restricted Data:** Under no circumstances may employees paste, upload, or feed customer PII, customer database queries, patient health information, financial transactions, or customer proprietary configurations into any public, consumer-tier generative AI platform (such as free web versions of ChatGPT, Claude, or Perplexity).
- **Proprietary Source Code:** Uploading proprietary, unreleased GlobalTech core source code or internal security vulnerability reports to third-party public AI services lacking an executed enterprise business agreement is a serious security breach.

---

## 6. Remote Network Security and Public Wi-Fi Guidelines
- **GlobalTech Zero Trust VPN:** All remote employees must connect via the corporate Cloudflare Zero Trust / WireGuard enterprise VPN client when accessing internal corporate applications, code repositories, or production clusters.
- **Untrusted Public Wi-Fi:** When connecting from airports, hotels, coffee shops, or public transit, employees must ensure that the corporate VPN is engaged prior to initiating any network connection.
- **Home Router Hardening:** Remote employees are required to change default administrative credentials on their home broadband Wi-Fi routers and maintain WPA3 or WPA2-AES encryption with strong network passphrases.

---

## 7. Security Incident Response & 1-Hour Reporting Window
- **Definition of Security Incident:** A security incident includes lost or stolen corporate laptops, compromised credentials, suspected phishing link interactions, unusual system behavior, unauthorized data access, or ransomware indicators.
- **Mandatory 1-Hour SLA:** Any employee who loses a corporate device or suspects a potential security breach must report the incident to the Security Operations Center (SOC) within **one (1) hour of discovery**:
  - Email: security@globaltech.internal
  - Urgent Slack Channel: `#security-incident-response`
  - 24/7 Security Hotline: 1-800-555-GT-SECU
- Swift reporting enables the SOC to remotely lock the stolen asset, revoke active Okta session tokens, and cycle cryptographic credentials before sensitive data can be exfiltrated.

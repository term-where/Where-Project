# Term Project Report — Secure Build

> Fill in every section. Keep the headings. Total **100 pts** (see rubric at the end).
> This is **team work** (2–3). Do not share your report with other teams.

## Cover

| Field | Value |
|---|---|
| Team name | Where|
| Members (name + ID) | Hathaichanok Yimjan (6631503045), Korrakit Lhakdee (6631503102) |
| Target application |NoteVault (Python/Flask, starter-app)|
| Repository URL |https://github.com/term-where/Where-Project.git , |
| Date | 6 November 2026 |

## AI-tool usage disclosure
*Academic integrity: state how you used any AI tools (ChatGPT, Copilot, etc.) — e.g. searching, coding, translating, drafting. "None" is a valid answer.*

| Tool | How it was used |
|---|---|
| Claude | Assisted with explanations and earlier report drafts; retain only uses that actually occurred. |
| ChatGPT | Reviewed the supplied source, report and screenshots; helped draft Sections 1–5 and proposed remediation. |
| Team verification | The team supplied local test screenshots. Implementation, commits and post-fix verification must be recorded from the team's actual work. |

---

## 1. Executive Summary
*(½ page) What the app is, how many findings by severity, and the overall risk before vs. after your fixes.*
Ans = NoteVault is a small note-sharing web application built with Flask and SQLite. Users can register, log in, create notes and search note content. A JSON endpoint retrieves notes by ID, and an admin endpoint lists accounts. Sessions use a JWT cookie. The current export endpoint runs an echo command rather than exporting stored notes.

We reviewed the source and tested the local team build. The supplied evidence includes the marker team=Where marker=4d820f632b4e. It demonstrates password-check bypass at login, JWT forgery using a hard-coded signing secret, OS command injection, SQL injection in search, registration role tampering, unauthorized note access and stored JavaScript execution. The cookie response also lacks explicit security attributes.

The assessment tracks 12 finding IDs. F-09 was assessed using pip-audit 2.10.1 against requirements.txt. The tool reported 81 vulnerability entries across seven packages. The scan output includes duplicate advisory IDs, so this total is not presented as 81 unique vulnerabilities. Severity and applicability to NoteVault remain under review.F-12 is limited here to root execution; a separate claim about secrets baked into an image requires Dockerfile/image inspection. Severity is a qualitative team assessment, not a calculated CVSS score.

| Provisional severity | Count | Finding IDs |
|---|---:|---|
| Critical | 2 | F-03, F-04 |
| High | 5 | F-01, F-05, F-06, F-07, F-08 |
| Medium | 4 | F-02, F-10, F-11, F-12 |
| Pending severity assessment | 1 | F-09 — dependency scan completed|

Before remediation, overall risk is assessed as Critical because a forged admin JWT can be chained with command injection to execute commands as root inside the application container. This does not demonstrate host compromise or a container escape. The login SQLi screenshot demonstrates bypass of password verification, but does not establish admin impersonation because the JWT subject is taken from the submitted username.

Remediation is in progress. The proposed changes address password hashing, query parameterization, token security, authorization, output escaping, dependency maintenance and runtime configuration. Residual risk after remediation has not yet been verified.


---

## 2. System Scope & Function
- What the application does; in-scope components and endpoints.
- **Data-Flow Diagram (DFD):** processes, data stores, external entities, **trust boundaries** (insert image).
Ans = Application components

| Component | Function |
|---|---|
| Browser / HTTP client | Sends credentials, cookies, note content and query parameters. |
| Flask application | Processes requests, verifies sessions, applies authorization and generates responses. |
| SQLite users table | Stores account names, password hashes and roles. |
| SQLite notes table | Stores note IDs, owners, titles and bodies. |
| OS subprocess | Executes the export command in the vulnerable implementation. |
| Build/runtime configuration | requirements.txt, Dockerfile and docker-compose.yml; configuration files beyond the pasted source require inspection. |

In-scope routes
| Route | Purpose |
|---|---|
| GET / | Login/register forms or the signed-in user's note list. |
| POST /register | Account registration. |
| POST /login | Credential verification and JWT cookie issuance. |
| GET /logout | Cookie deletion. |
| POST /notes | Create a note for the signed-in identity. |
| GET /api/notes/<id> | Retrieve a note by ID. |
| GET /search | Search note bodies. |
| GET /admin | List accounts for an admin identity. |
| GET /export | Run a placeholder export command. |

The database path is /tmp/notevault.db. The Docker host OS and course submission platform are outside the active test scope.

**Data-Flow Diagram (DFD):**

![alt text](<img/notevault-dfd f2.svg>)

| Boundary | Security meaning |
|---|---|
| B1: client to server | Credentials, cookies and input are untrusted until checked. |
| B2: application to database | SQL parameters must remain data; ownership restrictions must be enforced. The two logical tables share one SQLite file. |
| B3: application to shell | Untrusted request values must not become shell syntax. |
| B4: container to host | Container isolation limits scope; root in the container increases impact but does not prove host access. |



---

## 3. Threat Model — STRIDE  *(20 pts)*

| Element / data flow | S | T | R | I | D | E | Top threat & mitigation |
|---|---|---|---|---|---|---|---|
| Login — `/login` (B1→B2) | ✓ | ✓ | — | — | — | — | **F-02: SQL injection bypasses password verification.** Use a parameterized account lookup, verify the password hash, and issue the JWT for the verified database username. |
| Session cookie — JWT (B1) | ✓ | ✓ | — | ✓ | — | ✓ | **F-03: A hard-coded signing secret enables admin token forgery.** Use a strong runtime secret, allow only HS256, and require token expiration. |
| Password storage — `users` (B2) | — | — | — | ✓ | — | — | **F-01: Unsalted MD5 enables fast offline password guessing after hash disclosure.** Replace MD5 with Argon2id using a unique salt for each password. |
| Registration — `/register` (B1→B2) | — | ✓ | — | — | — | ✓ | **F-06: Client-supplied roles allow registration as admin.** Assign the `user` role server-side and reject unauthorized role changes. |
| Note retrieval — `/api/notes/<id>` (B1→B2) | — | — | — | ✓ | — | — | **F-07: Missing ownership checks expose other users’ notes.** Retrieve notes using both the note ID and authenticated owner. |
| Note rendering — `/` and `/search` (B1) | ✓ | ✓ | — | ✓ | — | — | **F-08: Stored note content executes JavaScript in the browser.** Use fixed, autoescaped templates and avoid marking user content as safe. Cross-user exposure requires further verification. |
| Search — `/search` (B1→B2) | — | ✓ | — | ✓ | — | — | **F-05: SQL injection discloses usernames and password hashes.** Bind the owner and search pattern as SQL parameters. |
| Export — `/export` (B3) | — | ✓ | — | ✓ | ✓ | ✓ | **F-04: Authenticated command injection executes OS commands inside the container.** Remove shell execution and allow-list supported formats. |
| Dependencies — `requirements.txt` | — | ✓ | — | ✓ | ✓ | ✓ | **F-09: Dependency scanning reports known vulnerabilities.** Review advisories for applicability, update affected packages, and rescan. The categories shown are potential impacts, not demonstrated exploits. |
| Flask runtime — debug mode | — | — | — | ✓ | — | — | **F-10: Debug mode exposes sensitive diagnostic information.** Disable debug and use a production WSGI server. Debug-console exploitation has not been demonstrated. |
| Session cookie attributes (B1) | ✓ | — | — | ✓ | — | — | **F-11: Missing cookie attributes increase session exposure.** Set HttpOnly, Secure and an explicit SameSite policy; use HTTPS. |
| Container privileges (B4) | — | ✓ | — | ✓ | ✓ | ✓ | **F-12: Root execution increases the impact of application compromise.** Run as a dedicated non-root user with restricted permissions. Host compromise has not been demonstrated. |
| Security event logging | — | — | ✓ | — | — | — | **Limited security logging makes actions difficult to investigate.** Record authentication and authorization events without passwords, tokens or note bodies. This is a design concern rather than an additional confirmed finding. |

Trust boundaries: B1 = Client ↔ Application; B2 = Application ↔ Database; B3 = Application ↔ OS shell; B4 = Container ↔ Host.

STRIDE: S = Spoofing, T = Tampering, R = Repudiation, I = Information Disclosure, D = Denial of Service, E = Elevation of Privilege.

*Then rank the top 5 risks by likelihood × impact.*

| Rank | Risk | Finding | Likelihood | Impact | Overall risk |
|---|---|---|---|---|---|
| 1 | OS command injection inside the container | F-04 | High | Critical | Critical |
| 2 | Forged admin JWT using the hard-coded secret | F-03 | High | Critical | Critical |
| 3 | Registration as admin through role tampering | F-06 | High | High | High |
| 4 | Search SQL injection exposing account hashes | F-05 | High | High | High |
| 5 | Unauthorized access to other users’ notes | F-07 | High | High | High |

---

## 4. Vulnerability Findings  *(25 pts)*

One block per finding (copy as needed):

### Finding F-01 — Unsalted MD5 Password Storage

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-916, CWE-759 / A04 Cryptographic Failures |
| Severity | High |
| Location | app.py: seed(), register(), login() |
| Root cause | Passwords use a fast, unsalted MD5 digest. |
| Reproduction | Inspect seed(), register() and login() in app.py. Confirm that passwords are hashed using hashlib.md5(...).hexdigest() without a per-password salt. |
| Observed result | Hashcat recovered both NoteVault seed passwords, alicepw and admin123. The output shows MD5 mode 0, Status: Cracked, and Recovered: 2/2 (100%). |
| Impact | Disclosure of hashes enables fast offline guessing, especially for weak or reused passwords. |
| Mitigation | Use Argon2id. Recreate only disposable lab seed data; for retained accounts use a documented migration/reset process. |
| Evidence | Hashcat screenshot showing both recovered hash–password pairs and team member ID 6631503102. |

![alt text](img/week03-task5-hashcat-cracked.png)

Finding F-02 — SQL Injection in Login

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-89 / A05 Injection |
| Severity | Medium, provisional: proven password-check bypass; admin takeover not demonstrated through this payload. |
| Location | app.py: login() |
| Root cause | The submitted username is interpolated into SQL. |
| Reproduction | Submit username `admin'-- ` with an incorrect password to POST /login, then follow the redirect with the returned cookie. |
| Observed result | The page shows a signed-in identity containing the SQL payload. The issued JWT uses the submitted username rather than the matched database username. |
| Impact | Credential verification is bypassed and a session is issued for an unvalidated identity. Do not describe this screenshot as admin impersonation. |
| Mitigation | Parameterize the account lookup, verify the stored hash and issue the token for the canonical database username. |

![alt text](img/f02-sqli-login.png)

Finding F-03 — JWT Forgery Using a Hard-coded Signing Secret

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-321 / A04 Cryptographic Failures; authentication impact also relates to A07. |
| Severity | Critical in combination with F-04. |
| Location | SECRET constant, current_user(), login() |
| Root cause | The HS256 signing secret is a predictable constant distributed with the source. |
| Reproduction | In the local lab, sign an HS256 JWT containing sub=admin using the starter secret; send it as the session cookie to / and /admin. |
| Observed result | The supplied screenshot shows admin notes, the team marker and the user listing without an admin password. |
| Impact | Admin impersonation, sensitive-data disclosure and access to authenticated command injection. |
| Mitigation | Generate a strong runtime secret, rotate the old key, allow only HS256 and require token expiry. |
| Limitation | The successful request used HS256. Generating an unsigned token does not prove that alg=none was accepted. |

![alt text](img/f03-admin-dump.png)

Finding F-04 — OS Command Injection in Export

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-78 / A05 Injection |
| Severity | Critical |
| Location | app.py: export() |
| Root cause | fmt is concatenated into subprocess.run(..., shell=True). |
| Prerequisite | A session, obtained normally or through another finding. |
| Reproduction | With a lab session, request /export?fmt=txt;id and /export?fmt=txt;whoami. The supplied evidence also reads /etc/passwd inside the lab container. |
| Observed result | Output includes uid=0 and root, confirming injected commands run in the container. |
| Impact | Arbitrary command execution with the application process's privileges. No host compromise is demonstrated. |
| Mitigation | Implement export in Python without a shell; allow-list supported formats and run as non-root. |

![alt text](<img/f04-cmd-injection 1.png>)

![alt text](<img/f04-cmd-injection 1.1.png>)

Finding F-05 — SQL Injection in Search

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-89 / A05 Injection |
| Severity | High |
| Location | app.py: search() |
| Root cause | The SQL query interpolates both user identity and the search term. |
| Reproduction | As Alice, submit q=`zzz' UNION SELECT id,username,password FROM users-- ` using URL encoding. |
| Observed result | The response shows usernames and MD5 hashes from users rather than only Alice's matching notes. |
| Impact | Account-hash disclosure and bypass of the intended note-search restriction. |
| Mitigation | Bind owner and LIKE pattern as SQL parameters. |

![alt text](img/f05-sqli-search.png)

Finding F-06 — Registration Role Mass Assignment

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-915 / A01 Broken Access Control |
| Severity | High |
| Location | app.py: register() |
| Root cause | Registration accepts role directly from form/JSON input. |
| Reproduction | Register a new local account with role=admin; log in as that account and request /admin. |
| Observed result | The evil account is recorded as admin and can retrieve the user listing. |
| Impact | Unauthenticated self-provisioning of an administrative account. |
| Mitigation | Ignore client-supplied roles and assign user server-side. Protect separate role-administration operations. |

![alt text](img/f06-mass-assignment.png)

Finding F-07 — IDOR in Note Retrieval

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-639 / A01 Broken Access Control |
| Severity | High |
| Location | app.py: api_note() |
| Root cause | The query checks note ID without checking note ownership. |
| Reproduction | Log in as Alice and request /api/notes/2 and /api/notes/3. |
| Observed result | Responses disclose admin-owned notes and team=Where marker=4d820f632b4e. |
| Impact | Cross-account note disclosure. The apparent production password is seeded lab content, not a verified real production credential. |
| Mitigation | Query by both note ID and authenticated owner. Return a consistent 404 for missing or inaccessible notes. |

![alt text](img/f07-idor.png)

Finding F-08 — Stored Cross-Site Scripting

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-79 / A05 Injection |
| Severity | High, provisional and dependent on victim exposure. |
| Location | home(): HTML concatenation and notes_html safe rendering; search() also builds template source from stored values. |
| Root cause | User-controlled note content is treated as trusted HTML. |
| Reproduction | As Alice, save body `<img src=x onerror=alert('XSS-Where')>` and open the home page in the signed-in browser. |
| Observed result | The supplied browser screenshot shows the XSS-Where alert. |
| Impact | Stored JavaScript executes in the application origin. Evidence demonstrates execution in the injecting user's session; cross-user delivery has not been established. |
| Mitigation | Render structured note data through a fixed, autoescaped template. Never concatenate note values into template source. |

![alt text](img/f08-stored-xss.png)

Finding F-09 — Outdated Dependency Assessment

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-1395 — Dependency on Vulnerable Third-Party Component / A03 — Software Supply Chain Failures |
| Severity | Pending advisory severity and applicability assessment; dependency scan completed. |
| Location | starter-app/requirements.txt |
| Observation | The application pins Flask 2.0.1, Werkzeug 2.0.1, Jinja2 3.0.1, PyJWT 1.7.1, requests 2.25.1 and urllib3 1.26.4. The scan also reports the transitive dependency idna 2.10. |
| Reproduction | Run `/tmp/notevault-audit/bin/pip-audit -r requirements.txt --format columns --output f09-dependency-audit.txt`, then run `cat f09-dependency-audit.txt`. |
| Observed result | pip-audit 2.10.1 reported 81 vulnerability entries across seven packages. The output includes package names, installed versions, advisory IDs and available fix versions. Duplicate advisory IDs appear in the output, so the total is not presented as 81 unique vulnerabilities. |
| Evidence | Attached dependency-scan screenshots show the scan command, summary and advisory table. The full output is saved in `starter-app/f09-dependency-audit.txt`. |
| Impact | Dependencies used by the application have reported security advisories. The actual impact depends on each advisory’s prerequisites and whether NoteVault uses the affected functionality. The scan alone does not demonstrate exploitation or establish High/Critical severity. |
| Mitigation | Review the reported advisories, upgrade affected dependencies to compatible patched versions, lock the resolved dependencies, and rescan. Test login, registration, notes, search and JWT handling after the updates. |

![alt text](<img/f09 Dependencies 1.png>)

![alt text](<img/f09 Dependencies 2.png>)

![alt text](<img/f09 Dependencies 3.png>)

Finding F-10 — Debug Mode Enabled

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-489 / A02 Security Misconfiguration |
| Severity | Medium, provisional. |
| Location | app.run(..., debug=True) |
| Reproduction | Inspect app.py and the startup log. |
| Observed result | The source enables debug mode; the supplied startup screenshot reports that the debugger is active. |
| Impact | Sensitive error details and unnecessary debugger exposure. Debug-console command execution has not been demonstrated. |
| Mitigation | Disable debug and deploy behind a production WSGI server. |

Evidence: [TO COMPLETE: save the supplied startup screenshot under an actual filename and insert its image link here.]

Finding F-11 — Missing Session Cookie Security Attributes

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-1004 (HttpOnly), CWE-614 (Secure), CWE-1275 (SameSite) / A02 Security Misconfiguration |
| Severity | Medium |
| Location | login(): resp.set_cookie() |
| Reproduction | Inspect Set-Cookie after a successful local login. |
| Observed result | The supplied header contains session and Path=/, without explicit HttpOnly, Secure or SameSite. Browser defaults may still apply. |
| Impact | Missing HttpOnly exposes the cookie to scripts; missing Secure permits transmission over HTTP; unspecified SameSite leaves behavior to browser defaults. |
| Mitigation | Set HttpOnly, Secure and an appropriate explicit SameSite policy; serve the deployed app over HTTPS. Add CSRF protection for state changes. |

Evidence: [TO COMPLETE: link the supplied combined XSS/cookie-header screenshot using its actual saved filename.]

![alt text](<img/f11-cookie flags.png>)

Finding F-12 — Application Commands Execute as Root in the Container

| Field | Value |
|---|---|
| CWE / OWASP 2025 | CWE-250 / A02 Security Misconfiguration |
| Severity | Medium as a separate hardening issue; amplifies F-04. |
| Location | Container runtime user; Dockerfile/Compose must be inspected to locate the configuration. |
| Reproduction | Review the id and whoami output from the export injection evidence. |
| Observed result | uid=0 and root. |
| Impact | Compromised application commands have root privileges inside the container. Host access is not established. |
| Mitigation | Configure a dedicated non-root user, writable data directory and restricted runtime permissions. |
| Limitation | No Dockerfile was supplied. This finding does not assert a separate secret baked into the image. The hard-coded source signing key is covered by F-03. |


---

## 5. Remediation *(25 pts)*

### 5.1 Implemented fixes and traceability

The fixes were implemented on branch `fix/security-remediation` and merged through [PR #4](https://github.com/term-where/Where-Project/pull/4) into `integration/sections-6-7`, then through [PR #3](https://github.com/term-where/Where-Project/pull/3) into `main`. The main remediation commit is [`374718e`](https://github.com/term-where/Where-Project/commit/374718e); GitHub Actions checkout pinning was added in [`536072d`](https://github.com/term-where/Where-Project/commit/536072d). The implementation details below reflect the **current `main` source**, not illustrative proposed code.

| Finding | Before remediation | Implemented remediation | Verification / caveat |
|---|---|---|---|
| F-01: MD5 password hashing | Fast unsalted MD5 hashes | Werkzeug `generate_password_hash(..., method="scrypt")` at registration and admin bootstrap; `check_password_hash` at login | `test_registration_cannot_grant_admin` checks Scrypt hash; old MD5 accounts require password reset and are not automatically migrated |
| F-02: Login SQL injection | User input interpolated into SQL | Parameterized lookup `WHERE username = ?`, then password verification | `test_login_sql_injection_rejected` expects 401; before screenshot `img/f02-sqli-login.png` |
| F-03: JWT forgery | Predictable source-code signing key | Requires runtime `APP_SECRET` of at least 32 characters; accepts only HS256 and requires `sub`, `iat`, `exp`; new tokens expire after one hour | `test_jwt_none_rejected` passes; old-key and expired-token tests not yet included |
| F-04: Shell command injection | Export format sent into `shell=True` command | Shell removed; `/export` only supports `fmt=txt`, queries current user's notes and returns a text response | `test_export_is_not_shell_execution` tests both rejected and accepted formats; before images `img/f04-cmd-injection 1.png` and `img/f04-cmd-injection 1.1.png` |
| F-05: Search SQL injection | Search term/owner placed in SQL source | Both values parameterized; LIKE metacharacters escaped | Review `search()` and manually retry original UNION payload; no dedicated automated SQLi regression for `/search` yet |
| F-06: Role mass assignment | Client-controlled registration role | New accounts always receive server-side `user` role | Role regression test and `/admin` returns 403 for non-admin account |
| F-07: IDOR | Lookup by note ID without owner validation | Lookup requires `id = ? AND owner = ?`, otherwise returns 404 | `test_idor_rejected` passes with two users |
| F-08: Stored XSS | Concatenation of stored content into HTML/template source | Fixed `home.html` and `search.html` templates with Jinja HTML escaping | `test_xss_is_escaped_on_home_and_search` passes |
| F-09: Vulnerable dependencies | Old pins, including Flask 2.0.1 and PyJWT 1.7.1 | Updated `requirements.txt` to Flask 3.1.3, Werkzeug 3.1.9, Jinja2 3.1.6, PyJWT 2.15.1, requests 2.34.2, urllib3 2.8.0, Flask-WTF 1.2.2 | Trivy SCA passes on integrated CI; no full transitive lockfile committed |
| F-10: Debug mode | Flask debug enabled | `debug=False`; direct Python execution defaults to `127.0.0.1` | Flask development server still used in the container: do not claim production WSGI hardening |
| F-11: Weak cookie flags | JWT cookie lacked explicit restrictions | `HttpOnly`, `SameSite=Lax`, one-hour max age; `Secure` controlled by `COOKIE_SECURE` | Local HTTP defaults `COOKIE_SECURE=false`; HTTPS/Secure-cookie deployment remains to be demonstrated |
| F-12: Root container | Process started as root, secret hard-coded in Dockerfile | Dedicated `appuser` via Dockerfile `USER`; `APP_SECRET` supplied by runtime Compose environment | Trivy IaC passed; non-root `id` tested locally; verify final rebuilt image too |

Additional defensive controls: Flask-WTF CSRF protection and hidden tokens in all POST forms; separate `csrf_session` Flask cookie to avoid colliding with JWT cookie `session`; administrator endpoint does not expose password hashes; `initialize_db()` no longer drops tables; security headers include CSP, `X-Frame-Options` and `X-Content-Type-Options`. A redundant duplicate call to `CSRFProtect(app)` remains and should be cleaned up.

### 5.2 Representative before / after explanation

**SQL injection (F-02)**: Rather than joining a user-controlled username into SQL, the corrected code binds it as data:

```python
row = con.execute(
    "SELECT password FROM users WHERE username = ?",
    (username,),
).fetchone()
```

**Password storage (F-01)**: New password hashes use adaptive Scrypt rather than fast MD5:

```python
password_hash = generate_password_hash(password, method="scrypt")
valid = check_password_hash(stored_hash, password)
```

**IDOR (F-07)**: The note query checks both identity and resource ownership:

```python
note = con.execute(
    "SELECT id,owner,title,body FROM notes WHERE id = ? AND owner = ?",
    (nid, user),
).fetchone()
```

**Command injection (F-04)**: The handler no longer invokes `subprocess` or a shell. It returns a supported TXT export built from owner-scoped note records, rejecting `fmt=txt;id` with HTTP 400.

### 5.3 Post-fix verification and limitations

The team ran seven regression tests in Docker and obtained `Ran 7 tests ... OK`. They cover database persistence, command-injection rejection, IDOR, unsigned JWT rejection, login SQL injection, role enforcement and HTML escaping. These seven tests do **not** exhaustively test all 12 findings. The current `main` branch also has successful GitHub Actions runs after PR integration, covering Semgrep, Trivy SCA + IaC and Gitleaks. Capture a screenshot of a final `main` test run and CI run for submission.

Remaining work includes negative tests for expired/old-key JWTs and search SQL injection, HTTPS with `COOKIE_SECURE=true`, production WSGI hosting, persistent storage, server-side session revocation and login rate limiting. The intended outcome is a hardened **local training build**, not a claim of production readiness.

---

## 6. Supply-Chain Hardening *(15 pts)*

### 6.1 CycloneDX SBOM

An SBOM was generated using Trivy from an earlier `starter-app-notevault:latest` image and saved as [`starter-app/sbom.json`](starter-app/sbom.json). The original recorded verification reported CycloneDX 1.7 and 483 components. The evidence screenshot is `img/sec6/01-sbom-verification.png`. An SBOM inventories packages but is not proof that the artifact is vulnerability-free.

**Important revision:** The committed SBOM predates the final remediation. Its component count and contents must not be represented as the verified inventory of the final `main` image.

### 6.2 Cosign signing and verification

The team used Cosign `sign-blob` to sign an exported image TAR and `verify-blob` to verify it against [`starter-app/cosign.pub`](starter-app/cosign.pub) and [`starter-app/notevault.sigstore.json`](starter-app/notevault.sigstore.json). The original verification screenshot is `img/sec6/02-cosign-verified.png` and records `Verified OK` and exit code 0. The private key is intentionally excluded from Git.

Signing a **TAR blob** is not equivalent to registry-based signing of an image digest. Signature verification supports integrity relative to a trusted key; it does not certify the security of the image contents.

### 6.3 SLSA self-assessment

This project does not yet demonstrate trusted build provenance and therefore makes **no claim to SLSA Build Level 1 or higher**. An SBOM, a verified blob signature and passing security scanners are valuable controls but do not, by themselves, provide reproducible or independently attested build provenance.

### 6.4 Final artifact evidence still needed

Because the remediation is now merged, the final-release procedure should be carried out **on the new image**: (1) rebuild from final `main`, (2) create a fresh CycloneDX SBOM, (3) export and sign the exact new artifact, (4) verify its signature, (5) record its SHA-256 digest, tool versions and verification logs, then (6) update this report and artifacts accordingly. Do not claim completion until those outputs actually exist.

**Existing evidence:** [`sbom.json`](starter-app/sbom.json), [`cosign.pub`](starter-app/cosign.pub), [`notevault.sigstore.json`](starter-app/notevault.sigstore.json), and two Section 6 screenshots.

---

## 7. Security CI Pipeline *(10 pts)*


### 7.1 GitHub Actions Security Pipeline

An automated security pipeline was implemented for NoteVault using GitHub Actions. It includes Semgrep for static application security testing, Trivy for dependency and configuration scanning, and Gitleaks for Git history secret scanning.

**Repository:** https://github.com/term-where/Where-Project

**Workflow:** `.github/workflows/security-ci.yml`

**Integration Pull Request:** https://github.com/term-where/Where-Project/pull/3

**Remediation Pull Request:** https://github.com/term-where/Where-Project/pull/4

### 7.2 Results Before Remediation

The initial security scans identified application security findings, vulnerable dependencies and insecure Dockerfile configurations.

| Security Check | Result Before Remediation |
|---|---|
| Semgrep — SAST | FAIL — 34 blocking findings reported |
| Trivy — SCA | FAIL — Dependency vulnerabilities detected |
| Trivy — IaC | FAIL — Two Dockerfile misconfigurations detected |
| Gitleaks — Secrets | PASS — No secret finding reported |
| Trivy Security Gate | FAIL — Exit code 1 |

The 34 Semgrep findings are scanner results and are not presented as 34 distinct, independently confirmed vulnerabilities.

**Evidence — Failed Workflow Before Remediation**

![alt text](../../where-ptoject/Where-Project-1/img/05-ci-before-fail.jpg)

**Semgrep Findings**

Semgrep reported insecure application code, including Flask debug mode being enabled with `debug=True`.


**Trivy Security Gate**

The Trivy security gate reported unsuccessful SCA and IaC outcomes and exited with code 1.

```text
SCA result: failure
IaC result: failure
Security Gate FAILED
Process completed with exit code 1.
```


**Gitleaks Secret Scanning**

Gitleaks completed successfully without a reported secret finding. This result applies to the scanner configuration and Git history examined; it does not guarantee that every sensitive value has been identified.


### 7.3 Dockerfile Configuration Findings

The initial Trivy IaC scan identified two Dockerfile misconfigurations.

| Rule ID | Severity | Finding |
|---|---|---|
| DS-0002 | HIGH | The container did not explicitly use a non-root user. |
| DS-0031 | CRITICAL | `APP_SECRET` was defined in a Dockerfile environment variable, creating a potential secret-exposure risk. |

**Initial IaC Scan Summary:**

- Total checks: 20
- Successful checks: 18
- Failed checks: 2
- HIGH findings: 1
- CRITICAL findings: 1


The corresponding remediation introduces a non-root container user and removes the baked-in application secret. Secrets must be supplied through runtime configuration.

### 7.4 Results After Remediation

Following the remediation changes, the screenshot of PR #3 showed successful results for all three security jobs.

| Security Job | Result on PR #3 |
|---|---|
| SAST — Semgrep | PASS |
| SCA + IaC — Trivy | PASS |
| Secrets — Gitleaks | PASS |

**Evidence — Successful Checks on PR #3**

![alt text](../../where-ptoject/Where-Project-1/img/06-ci-after-pass.png)

The screenshot demonstrates that the tested PR revision passed the configured security checks. It does not establish that a subsequent workflow run on `main` passed, or that every application vulnerability has been resolved.

The Semgrep configuration excludes a Django-specific CSRF rule that is not applicable to this Flask application. This exclusion must remain documented and must not be interpreted as evidence that Flask CSRF protection has been tested.

Application regression tests and attack re-tests are documented separately in Section 5.

### 7.5 Security Gate Configuration

The workflow uses command exit codes to report security failures.

| Tool | Failure Configuration |
|---|---|
| Semgrep | `--error` reports failure when blocking findings are detected. |
| Trivy SCA | `exit-code: '1'` reports failure for findings meeting the configured HIGH/CRITICAL threshold. |
| Trivy IaC | `exit-code: '1'` reports failure for findings meeting the configured HIGH/CRITICAL threshold. |
| Gitleaks | `--exit-code 1` reports failure when potential secrets are detected. |

The Trivy scanning steps use `continue-on-error: true` so both SCA and IaC scans can run even when one fails.

A final gate checks `steps.sca.outcome` and `steps.iac.outcome`. If either outcome is not `success`, the gate exits with code 1. This also prevents an unsuccessful scan caused by an operational error from being treated as a passing result.

A failed workflow marks the security checks as unsuccessful. Preventing a merge additionally requires repository rules or branch protection that make these checks mandatory.

### 7.6 Conclusion and Next Steps

The evidence shows an earlier failing workflow and later successful security checks on PR #3. This demonstrates detection of security issues and successful execution of the configured checks after changes were made.

Passing CI is one part of verification. The team must also retain attack re-test results, confirm normal application functionality, and review the scope and configuration of each scanner.

Before the final release, the team should verify the final source revision, rebuild the image, regenerate its SBOM, and sign and verify the final artifact. Workflow run links and tested commit IDs should be retained with the evidence.
---

## 8. Conclusion & Reflection *(5 pts — clarity)*

### 8.1 Conclusion and residual risks

NoteVault's intentionally vulnerable version exposed weaknesses in authentication, access control, SQL query construction, shell execution, stored HTML content, password hashing, dependency maintenance and Docker configuration. The pre-fix evidence includes administrative JWT forgery and command execution **inside the lab container**; host compromise was not established.

The merged code now uses parameterized queries, Scrypt password hashes, restricted JWT validation and expiration, note ownership checks, autoescaped templates, shell-free export, non-root container execution, runtime secrets and CSRF protection. Seven local regression tests passed, and the post-merge GitHub Actions checks passed for Semgrep, Trivy and Gitleaks.

Residual risk remains. The current application uses the Flask development server, its local HTTP configuration does not set `Secure` on cookies by default, its JWT logout does not provide immediate server-side revocation, it lacks demonstrated login rate limiting, and the container configuration has no persistent SQLite volume. The committed SBOM/signature files are from a previous image and have not been proven to match the final remediated build. Accordingly, this is a **hardened authorized training implementation**, not a production-ready deployment.

### 8.2 Next improvements

1. Add a `.dockerignore`, inspect the final image for unintended files, and remove the duplicate CSRF initialization.
2. Deploy with HTTPS, secure cookie settings, production WSGI hosting, secure secrets management and persistent database storage.
3. Extend negative tests for search SQL injection, invalid/expired JWTs, CSRF, cookie attributes and account-lockout/rate-limit behavior.
4. Build the **final** image again, generate its SBOM, sign and verify that exact artifact, record its digest and consider provenance attestations.
5. Capture final screenshots tied to the same commit and configure required security checks for future pull requests.

### 8.3 Lessons learned

Authentication does not replace per-object authorization. Prepared SQL statements isolate user data from SQL syntax. Autoescaped templates prevent note content from being interpreted as executable HTML. Eliminating shell execution prevents command injection at its source. Adaptive password hashing is necessary for protecting stored credentials.

We also learned to differentiate **demonstrated exploits**, **scanner findings**, **implemented fixes** and **remaining limitations**. Scans can pass while untested risks remain, and an SBOM or signature must correspond to the specific artifact being delivered. Reproducible links between evidence, commits, tests, CI results and the release artifact make the team's security claims auditable.

---

## Appendix
- Tools used, references (OWASP/CWE links), and the team's task split.
Ans = 
A. Tools Used

| Tool | Purpose |
|---|---|
| Visual Studio Code | Editing application code, configuration files and the report. |
| Git and GitHub | Version control, team collaboration and storing project evidence. |
| Docker and Docker Compose | Building and running the NoteVault application. |
| Browser and curl | Testing application endpoints and reproducing vulnerabilities. |
| Hashcat | Demonstrating offline recovery of the seeded MD5 passwords. |
| pip-audit | Identifying known vulnerabilities in Python dependencies. |
| Semgrep | Static application security testing in CI. |
| Trivy | Dependency and container configuration scanning, and CycloneDX SBOM generation. |
| Gitleaks | Scanning Git history for potential secrets. |
| Cosign | Signing and verifying exported artifacts. |
| GitHub Actions | Running automated security checks and enforcing security gates. |

B. References

| Reference | Link |
|---|---|
| OWASP Top 10:2025 | https://top10.owasp.org/2025/ |
| CWE-916 — Password Hash with Insufficient Computational Effort | https://cwe.mitre.org/data/definitions/916.html |
| CWE-759 — Use of a One-Way Hash without a Salt | https://cwe.mitre.org/data/definitions/759.html |
| CWE-89 — SQL Injection | https://cwe.mitre.org/data/definitions/89.html |
| CWE-321 — Use of Hard-coded Cryptographic Key | https://cwe.mitre.org/data/definitions/321.html |
| CWE-78 — OS Command Injection | https://cwe.mitre.org/data/definitions/78.html |
| CWE-915 — Improperly Controlled Modification of Dynamically-Determined Object Attributes | https://cwe.mitre.org/data/definitions/915.html |
| CWE-639 — Authorization Bypass Through User-Controlled Key | https://cwe.mitre.org/data/definitions/639.html |
| CWE-79 — Cross-Site Scripting | https://cwe.mitre.org/data/definitions/79.html |
| CWE-1395 — Dependency on Vulnerable Third-Party Component | https://cwe.mitre.org/data/definitions/1395.html |
| CWE-489 — Active Debug Code | https://cwe.mitre.org/data/definitions/489.html |
| CWE-1004 — Sensitive Cookie Without HttpOnly Flag | https://cwe.mitre.org/data/definitions/1004.html |
| CWE-614 — Sensitive Cookie in HTTPS Session Without Secure Attribute | https://cwe.mitre.org/data/definitions/614.html |
| CWE-1275 — Sensitive Cookie with Improper SameSite Attribute | https://cwe.mitre.org/data/definitions/1275.html |
| CWE-250 — Execution with Unnecessary Privileges | https://cwe.mitre.org/data/definitions/250.html |
| OWASP Password Storage Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html |
| CycloneDX | https://cyclonedx.org/ |
| Sigstore Cosign Documentation | https://docs.sigstore.dev/ |
| SLSA Specification | https://slsa.dev/spec/ |

C. Team Task Split
| Team Member | Assigned Sections | Responsibilities |
|---|---|---|
| Hathaichanok Yimjan — 6631503045 | Sections 1–4 and 8 | Prepared the executive summary, system scope and DFD, STRIDE threat model, vulnerability findings and supporting evidence, and conclusion and reflection. |
| Korrakit Lhakdee — 6631503102 | Sections 5–7 | Responsible for implementing and documenting remediation, supply-chain hardening with SBOM and artifact signing, and the GitHub Actions security pipeline. |


---

## Grading rubric (100)

| Criterion | Pts |
|---|---|
| Threat model quality & completeness (§3) | 20 |
| Vulnerability findings — correctness, CWE/OWASP mapping, depth (§4) | 25 |
| Remediation quality — correct, minimal, well-explained (§5) | 25 |
| Supply-chain hardening — SBOM + signing + provenance (§6) | 15 |
| CI pipeline — works, fails build appropriately (§7) | 10 |
| Presentation & report clarity (§1, §8) | 5 |

*All work stays within the [ethics policy](../ETHICS.md).*

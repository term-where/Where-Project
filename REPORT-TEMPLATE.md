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

## 5. Remediation  *(25 pts)*

Per finding: the fix, **before/after** code, and the commit that implements it.

### Fix for F-01
```diff
- vulnerable line
+ fixed line
```
- **Why this fixes it:** …
- **Commit:** `<hash>`
- **Proof the exploit now fails:** (screenshot)
Ans = Status: proposed implementation, not verified fixes. The examples below describe changes to make against the actual repository. They are not exact git diffs. For each finding, replace the pending commit field with a real hash and attach actual post-fix results. Do not label a proposed test as passed.

Fix for F-01 — Argon2id Password Storage
Before: seed(), register() and login() compute MD5 digests.

After: add a compatible, scanned version of argon2-cffi to the dependency lock. Keep import hashlib because team_marker() uses SHA-256.

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

ph = PasswordHasher()

# In seed(): replace each MD5 seed hash with ph.hash("alicepw")
# or ph.hash("admin123"), respectively.
# In register(), after validating password is a nonempty string:
password_hash = ph.hash(password)
# Store password_hash with a parameterized INSERT.

# In login(), use the account lookup shown in F-02, then:
if row:
    try:
        ph.verify(row["password"], password or "")
    except (VerificationError, InvalidHashError):
        row = None

 Why: Argon2id uses a per-password salt and configurable resource cost. Apply the change to every password-writing and verification path. The pasted app's seed() destroys existing tables; use that only for disposable lab data, not as a production migration strategy. Retained MD5 accounts need an explicitly implemented migration or password reset; the snippet does not implement migration.

Commit: [TO COMPLETE]. Verification: correct passwords succeed, wrong passwords fail, identical passwords produce different hashes, and stored hashes begin with $argon2id$. Actual result: [TO COMPLETE].

Fix for F-02 — Parameterized Login and Canonical Identity
Before: username is interpolated into SQL and copied into the JWT subject.

After: validate inputs, query using a bound parameter, verify the Argon2 hash as described in F-01, and use the database username when issuing the token.

row = con.execute(
    "SELECT id, username, password, role FROM users WHERE username = ?",
    (username,),
).fetchone()
# Perform ph.verify() here. If row is absent or verification fails:
# return "login failed", 401
# If verification succeeds, issue JWT with sub=row["username"].

Why: input cannot change SQL syntax, and the identity comes from a verified record. These login changes overlap with F-01; reference the same commit where appropriate rather than presenting incompatible patches.

Commit: [TO COMPLETE]. Verification: the original injection returns 401, correct Alice credentials still work, and the token identifies Alice. Actual result: [TO COMPLETE].

Fix for F-03 — Runtime Secret and Expiring JWTs
Before: a shared source constant signs tokens; no expiration is issued or required.

After: provision a random secret outside the repository and fail startup if it is missing. This example assumes migration to a compatible modern PyJWT version.

from datetime import datetime, timedelta, timezone

SECRET = os.environ["NOTEVAULT_JWT_SECRET"]

# After successful login:
now = datetime.now(timezone.utc)
tok = jwt.encode(
    {"sub": row["username"], "iat": now, "exp": now + timedelta(minutes=30)},
    SECRET,
    algorithm="HS256",
)

# In current_user():
data = jwt.decode(
    tok, SECRET, algorithms=["HS256"],
    options={"require": ["sub", "exp"]},
)
# Reject non-string/empty sub; confirm the account still exists.
# Handle jwt.InvalidTokenError by returning None.

Why: the distributed old key no longer authorizes tokens, and a fixed algorithm and required expiry constrain token acceptance. Do not fall back to the old key when configuration is missing. Logout currently only deletes the browser cookie; immediate server-side revocation needs additional design.

Commit: [TO COMPLETE]. Verification: old-key tokens, unsigned tokens, expired tokens, tokens missing exp and invalid subjects are rejected; new valid sessions work. Actual result: [TO COMPLETE].

Fix for F-04 — Remove Shell Execution
Before: subprocess.run("echo exporting notes as " + fmt, shell=True, ...).

After: for the existing placeholder, return text directly and allow-list fmt. A real note export would also need an owner-scoped query.

fmt = request.args.get("fmt", "txt")
if fmt not in {"txt", "json"}:
    return jsonify(error="unsupported format"), 400
return app.response_class(
    "exporting notes as " + fmt + "\n",
    mimetype="text/plain",
)

Keep the authentication check. Remove subprocess import when unused. Why: no shell interprets request content.

Commit: [TO COMPLETE]. Verification: txt/json work; semicolon payloads return 400 without command output. Actual result: [TO COMPLETE].

Fix for F-05 — Parameterized Search
rows = con.execute(
    "SELECT id,title,body FROM notes WHERE owner = ? AND body LIKE ?",
    (user, "%" + term + "%"),
).fetchall()

Why: owner and term remain values, not SQL syntax. Also apply F-08 to search rendering.

Commit: [TO COMPLETE]. Verification: the original UNION input does not reveal users/hashes; normal searches still find only the current user's notes. Actual result: [TO COMPLETE].

Fix for F-06 — Server-assigned Registration Role
Before: role is read from the submitted form or JSON.

After: assign role = "user" without accepting a client override. Use an allow-list of registration fields, validate username/password and enforce unique usernames with appropriate duplicate handling.

Why: users cannot choose an administrative role during public registration. Remove unauthorized admin accounts created during testing.

Commit: [TO COMPLETE]. Verification: register with role=admin and confirm the new account remains user and /admin returns 403. Actual result: [TO COMPLETE].

Fix for F-07 — Enforce Note Ownership

user = current_user()
if not user:
    return jsonify(error="auth required"), 401
con = db()
r = con.execute(
    "SELECT id,owner,title,body FROM notes WHERE id = ? AND owner = ?",
    (nid, user),
).fetchone()
con.close()
return jsonify(dict(r)) if r else (jsonify(error="not found"), 404)

Why: both the object identifier and owner must match the authenticated identity.

Commit: [TO COMPLETE]. Verification: Alice's own note returns 200; admin notes and nonexistent IDs return 404; anonymous requests return 401. Actual result: [TO COMPLETE].

Fix for F-08 — Autoescaped Rendering
Before: note strings are assembled into HTML and marked safe, or concatenated into template source.

After: replace {{ notes_html|safe }} in PAGE with a fixed loop and pass the row list as notes. Initialize notes=[] for anonymous requests.

<ul>
{% for note in notes %}
  <li>#{{ note.id }} <b>{{ note.title }}</b>: {{ note.body }}</li>
{% endfor %}
</ul>

# Home rendering: pass structured data, not an HTML string.
return render_template_string(
    PAGE, user=user, is_admin=bool(user and role_of(user) == "admin"),
    notes=rows,
)

# Search: use a fixed template too; never join note values into its source.
return render_template_string(
    '<a href="/">back</a><ul>{% for n in notes %}'
    '<li>{{ n.title }}: {{ n.body }}</li>{% endfor %}</ul>',
    notes=rows,
)

The home example assumes rows is initialized for all paths. Why: autoescaping treats note values as text rather than executable HTML or template source.

Commit: [TO COMPLETE]. Verification: the saved XSS payload displays as text without alert; both home and search remain functional. Actual result: [TO COMPLETE].

Fix for F-09 — Verified Dependency Updates
Proposed action: scan the original resolved environment, record advisories, choose compatible patched versions, create a reproducible lock and scan the rebuilt environment/image. Do not invent replacement version numbers or report a clean scan without results.

Commit: [TO COMPLETE]. Before/after package/advisory table and actual scan output: [TO COMPLETE]. Confirm modern PyJWT, Flask JSON parsing and Argon2 integration work together. Prefer request.get_json(silent=True) or explicit content-type handling for mixed form/JSON routes when adapting to updated Flask behavior.

Fix for F-10 — Disable Debug and Use a Production Server
Before: Flask's development server starts with debug=True.

Proposed action: disable debug, use a production WSGI server in the container, and explicitly initialize the database for that entry point. Importing app with a WSGI server will not execute the current main seed() block; blindly changing the command can leave the database uninitialized. Keep destructive demo seeding separate from normal startup.

Commit: [TO COMPLETE]. Exact Docker command/WSGI dependency and database initialization change: [TO COMPLETE after Dockerfile review]. Verification: no active debugger, generic error responses and a working initialized app. Actual result: [TO COMPLETE].

Fix for F-11 — Cookie Attributes and HTTPS

resp.set_cookie(
    "session", tok,
    httponly=True, secure=True, samesite="Lax", path="/",
)

Why: HttpOnly prevents ordinary script access to the cookie; Secure restricts transmission to HTTPS; an explicit SameSite policy reduces some cross-site request exposure. These do not replace XSS fixes or CSRF protection. Configure HTTPS for deployed verification; if local HTTP needs an exception, keep it explicit and limited to development.

Commit: [TO COMPLETE]. Verification: inspect the actual Set-Cookie header and confirm login/logout work in the target HTTPS environment. Actual result: [TO COMPLETE].

Fix for F-12 — Non-root Container Runtime
Proposed action: create a dedicated application user, switch USER before the runtime command and give it write access only to the intended SQLite directory. Check Compose user settings and mounted-volume ownership. Do not add a Dockerfile diff before reading the actual file. Keep signing keys outside source/image layers.

Why: a compromised process has fewer privileges inside the container. This supplements, rather than fixes, command injection.

Commit: [TO COMPLETE]. Exact Dockerfile/Compose changes: [TO COMPLETE]. Verification: runtime id reports a nonzero UID, database writes still work and the F-04 injection remains blocked. Actual result: [TO COMPLETE].

Remediation evidence checklist

| Required item | Current status |
|---|---|
| Actual corrected source and dependency files | Not supplied |
| Exact git diff against the repository | Pending implementation |
| Commit hashes referring to finding IDs | Not supplied |
| Post-fix exploit retests | Not supplied |
| Normal-function regression checks | Not supplied |
| Original and post-update SCA output | Not supplied |
| Dockerfile and Compose review | Not supplied |

References for checking the mapping and implementation:
- OWASP Top 10:2025: https://top10.owasp.org/2025/
- CWE definitions: https://cwe.mitre.org/data/index.html
- PyJWT documentation: https://pyjwt.readthedocs.io/
- Password storage guidance: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

---

## 6. Supply-Chain Hardening  *(15 pts)*
- **SBOM** (CycloneDX) generated — attach `sbom.json`, note component count.
- **Artifact signed & verified** with Cosign — paste the `cosign verify` output.
- One-paragraph **SLSA** self-assessment (which level, why).

---

## 7. Security CI Pipeline  *(10 pts)*
- Link to the GitHub Actions workflow (SAST + SCA + secret scanning).
- Screenshot of a build **failing** on a HIGH/CRITICAL finding.
- How the gate is configured (what fails the build).

---

## 8. Conclusion & Reflection  *(5 pts — clarity)*
- Residual risks and what you'd harden next.
- Lessons learned.

---

## Appendix
- Tools used, references (OWASP/CWE links), and the team's task split.

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

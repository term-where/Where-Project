"""Run: python -m unittest discover -s tests -v (inside NoteVault container)."""
import base64
import json
import re
import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("APP_SECRET", "local-test-key-of-at-least-32-characters-not-for-production")
import app as server


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB = os.path.join(self.tmp.name, "test.db")
        server.initialize_db()
        self.client = server.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def post_with_csrf(self, path, data):
        """Fetch a CSRF token and submit a form with the test client's session."""
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', page.data)
        self.assertIsNotNone(match, "CSRF hidden input missing from home.html")
        return self.client.post(path, data={**data, "csrf_token": match.group(1).decode()})

    def register_and_login(self, user="testuser", password="a-long-test-password-123"):
        self.assertEqual(self.post_with_csrf("/register", data={"username": user, "password": password, "role": "admin"}).status_code, 302)
        self.assertEqual(self.post_with_csrf("/login", data={"username": user, "password": password}).status_code, 302)

    def test_registration_cannot_grant_admin(self):
        self.register_and_login()
        with sqlite3.connect(server.DB) as con:
            self.assertEqual(con.execute("SELECT role FROM users WHERE username=?", ("testuser",)).fetchone()[0], "user")
            self.assertTrue(con.execute("SELECT password FROM users").fetchone()[0].startswith("scrypt:"))
        self.assertEqual(self.client.get("/admin").status_code, 403)

    def test_login_sql_injection_rejected(self):
        self.assertEqual(self.post_with_csrf("/login", data={"username":"admin' OR '1'='1", "password":"x"}).status_code, 401)

    def test_xss_is_escaped_on_home_and_search(self):
        self.register_and_login()
        payload = '<script>alert(1)</script>'
        self.post_with_csrf("/notes", data={"title": payload, "body": payload})
        self.assertNotIn(b"<script>", self.client.get("/").data)
        self.assertNotIn(b"<script>", self.client.get("/search?q=alert").data)

    
    def test_idor_rejected(self):
        self.register_and_login("alice2")

        response = self.post_with_csrf(
            "/notes",
            data={"title": "private", "body": "only alice"}
        )
        self.assertEqual(
            response.status_code, 302,
            f"Add note failed: {response.status_code} "
            f"{response.get_data(as_text=True)[:300]}"
        )

        with sqlite3.connect(server.DB) as con:
            row = con.execute(
                "SELECT id FROM notes WHERE owner = ?",
                ("alice2",)
            ).fetchone()

        self.assertIsNotNone(row, "Alice's note was not saved")
        note_id = row[0]

        self.client.get("/logout")
        self.register_and_login("bob2")

        response = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(response.status_code, 404)


    def test_jwt_none_rejected(self):
        def b64(obj):
            return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
        token = f'{b64({"alg":"none","typ":"JWT"})}.{b64({"sub":"admin"})}.'
        self.client.set_cookie("session", token)
        self.assertNotIn(b"Signed in as", self.client.get("/").data)

    def test_export_is_not_shell_execution(self):
        self.register_and_login()
        self.assertEqual(self.client.get("/export?fmt=txt;id").status_code, 400)
        self.assertEqual(self.client.get("/export?fmt=txt").status_code, 200)

    def test_db_survives_initialize(self):
        self.register_and_login()
        server.initialize_db()
        with sqlite3.connect(server.DB) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

"""Hosted authentication and storage isolation, using disposable databases only."""

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import time
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

import app
import tenant_context as tenants


class HostedIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer = "https://test-team.cloudflareaccess.com"
        cls.audience = "test-collection"

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        identity = tenants.AccessIdentity(self.issuer, self.audience)
        identity.keys = SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=self.key.public_key())
        )
        for name, value in {
            "HOSTED": True,
            "IDENTITY": identity,
            "USERS_ROOT": self.root,
            "PUBLIC_ORIGIN": "https://cards.example.com",
        }.items():
            patcher = patch.object(tenants, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ScannerHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def token(self, email="owner@example.com", **overrides):
        claims = dict(iss=self.issuer, aud=self.audience, exp=int(time()) + 300,
                      iat=int(time()), sub=email, email=email, type="app")
        claims.update(overrides)
        return jwt.encode(claims, self.key, algorithm="RS256")

    def request(self, route, token=None, method="GET", body=None, extra=None):
        connection = HTTPConnection(*self.server.server_address, timeout=10)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Cf-Access-Jwt-Assertion"] = token
        headers.update(extra or {})
        try:
            connection.request(method, route, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            data = response.read()
            return response.status, json.loads(data) if data.startswith(b"{") else data
        finally:
            connection.close()

    def test_signed_identity_and_invalid_tokens(self):
        self.assertEqual(self.request("/account", self.token("OWNER@example.com"))[1]["email"],
                         "owner@example.com")
        invalid = [None, "invalid", self.token(exp=int(time()) - 10),
                   self.token(aud="another-app"), self.token(iss="https://wrong.example.com"),
                   self.token(type="service"), self.token(email="invalid")]
        for token in invalid:
            with self.subTest(token=bool(token)):
                self.assertEqual(self.request("/account", token)[0], 401)
        forged = jwt.encode(dict(email="owner@example.com"), "untrusted" * 8, algorithm="HS256")
        self.assertEqual(self.request("/account", forged)[0], 401)

    def test_every_private_route_rejects_anonymous_and_forged_email_headers(self):
        for route in ["/", "/inventory/cards", "/decks", "/inventory/locations",
                      "/inventory/export.json", "/account", "/catalog/search"]:
            self.assertEqual(self.request(route, extra={"Cf-Access-Authenticated-User-Email":
                                                       "owner@example.com"})[0], 401)
        self.assertEqual(self.request("/inventory/set", method="POST", body={})[0], 401)
        self.assertEqual(self.request("/health"), (200, {"ok": True, "multi_user": True}))

    def test_new_user_is_empty_and_concurrent_requests_stay_separate(self):
        context = tenants.CURRENT_EMAIL.set("owner@example.com")
        try:
            app.inventory_database().set_quantity("card-1", 3)
            app.saved_deck_database().initialize()
        finally:
            tenants.CURRENT_EMAIL.reset(context)
        owner = self.token()
        friend = self.token("friend@example.com")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda token: self.request("/account", token), [owner, friend] * 6))
        self.assertEqual([value[1]["email"] for value in results],
                         ["owner@example.com", "friend@example.com"] * 6)
        self.assertEqual(self.request("/decks", friend)[1]["decks"], [])
        for email, expected in [("friend@example.com", 0), ("owner@example.com", 3)]:
            context = tenants.CURRENT_EMAIL.set(email)
            try:
                self.assertEqual(app.inventory_database().quantity("card-1"), expected)
                self.assertTrue(app.inventory_database().path.is_relative_to(self.root / tenants.tenant_id(email)))
            finally:
                tenants.CURRENT_EMAIL.reset(context)
        self.assertIsNone(tenants.CURRENT_EMAIL.get())
        with self.assertRaises(tenants.AuthenticationError):
            app.inventory_database()

    def test_decks_locations_evidence_and_import_previews_are_private(self):
        fingerprints = []
        evidence_paths = []
        for email, name, quantity in [("owner@example.com", "Owner", 2),
                                      ("friend@example.com", "Friend", 7)]:
            context = tenants.CURRENT_EMAIL.set(email)
            try:
                app.inventory_database().set_quantity("card-1", quantity)
                app.inventory_database().create_location(name)
                app.saved_deck_database().save(name, "1 Pikachu", 1, 1)
                fingerprints.append(app._inventory_import_fingerprint("update", {"card-1": 1}, {}))
                evidence_paths.append(tenants.scoped_path("ocr/reads.csv", Path("unused")))
            finally:
                tenants.CURRENT_EMAIL.reset(context)
        self.assertNotEqual(*fingerprints)
        self.assertNotEqual(*evidence_paths)
        for email, name in [("owner@example.com", "Owner"), ("friend@example.com", "Friend")]:
            context = tenants.CURRENT_EMAIL.set(email)
            try:
                self.assertEqual([deck.name for deck in app.saved_deck_database().decks()], [name])
                with app.inventory_database().connect() as connection:
                    self.assertEqual([row[0] for row in connection.execute("SELECT name FROM inventory_locations")], [name])
            finally:
                tenants.CURRENT_EMAIL.reset(context)

    def test_cross_site_writes_and_desktop_routes_are_blocked(self):
        token = self.token()
        for headers in [{"Origin": "https://evil.example"},
                        {"Sec-Fetch-Site": "cross-site"}, {"Content-Type": "text/plain"}]:
            self.assertEqual(self.request("/inventory/set", token, "POST", {}, headers)[0], 403)
        self.assertEqual(self.request("/desktop-session/status", token)[0], 404)


if __name__ == "__main__":
    unittest.main()

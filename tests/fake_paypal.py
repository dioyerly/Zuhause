#!/usr/bin/env python3
"""PayPal FALSO para pruebas locales (forma que ESPERAMOS de la API de Subscriptions; no verificada contra PayPal real).
Control: POST /__set {"sub": {id: {...}}, "tx": {id: [...]}, "firma_ok": bool, "reset": bool}"""
import json, sys, base64, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
ST = {"sub": {}, "tx": {}, "plan": {"P-TEST": {"id": "P-TEST", "name": "Zuhause mensual USD", "billing_cycles": [
    {"tenure_type": "TRIAL", "sequence": 1, "total_cycles": 1, "frequency": {"interval_unit": "DAY", "interval_count": 3}, "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": "USD"}}},
    {"tenure_type": "REGULAR", "sequence": 2, "total_cycles": 0, "frequency": {"interval_unit": "MONTH", "interval_count": 1}, "pricing_scheme": {"fixed_price": {"value": "9.00", "currency_code": "USD"}}}]}},
    "firma_ok": True, "llamadas": [], "creadas": 0, "ultimo_body": None}
AUTH = "Basic " + base64.b64encode(b"cid-test:secret-test").decode()
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _body(self):
        n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n) or b"{}"
        return raw.decode()
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/__llamadas": return self._j(200, ST["llamadas"])
        if self.headers.get("Authorization") != "Bearer TOK-PP": return self._j(401, {"name": "AUTHENTICATION_FAILURE"})
        ST["llamadas"].append(self.path)
        if p.startswith("/v1/billing/subscriptions/") and p.endswith("/transactions"):
            i = p.split("/")[-2]; return self._j(200, {"transactions": ST["tx"].get(i, [])}) if i in ST["sub"] else self._j(404, {})
        if p.startswith("/v1/billing/subscriptions/"):
            i = p.split("/")[-1]; return self._j(200, ST["sub"][i]) if i in ST["sub"] else self._j(404, {"name": "RESOURCE_NOT_FOUND"})
        if p.startswith("/v1/billing/plans/"):
            i = p.split("/")[-1]; return self._j(200, ST["plan"][i]) if i in ST["plan"] else self._j(404, {})
        self._j(404, {})
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path; raw = self._body()
        try: d = json.loads(raw)
        except Exception: d = {}
        if p == "/__set":
            if d.get("reset"): ST["sub"].clear(); ST["tx"].clear(); ST["llamadas"].clear(); ST["firma_ok"] = True; ST["creadas"] = 0
            ST["sub"].update(d.get("sub", {})); ST["tx"].update(d.get("tx", {}))
            if "firma_ok" in d: ST["firma_ok"] = bool(d["firma_ok"])
            return self._j(200, {"ok": True})
        if p == "/__ultimo": return self._j(200, ST["ultimo_body"])
        if p == "/v1/oauth2/token":
            if self.headers.get("Authorization") != AUTH: return self._j(401, {"error": "invalid_client"})
            return self._j(200, {"access_token": "TOK-PP", "expires_in": 32000})
        if self.headers.get("Authorization") != "Bearer TOK-PP": return self._j(401, {"name": "AUTHENTICATION_FAILURE"})
        if p == "/v1/billing/subscriptions":
            ST["creadas"] += 1; ST["ultimo_body"] = d; i = "I-NUEVA%04d" % ST["creadas"]
            return self._j(201, {"id": i, "status": "APPROVAL_PENDING", "plan_id": d.get("plan_id"), "links": [{"rel": "approve", "href": "http://paypal.example/approve?ba=" + i, "method": "GET"}]})
        if p == "/v1/notifications/verify-webhook-signature":
            return self._j(200, {"verification_status": "SUCCESS" if ST["firma_ok"] else "FAILURE"})
        self._j(404, {})
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()

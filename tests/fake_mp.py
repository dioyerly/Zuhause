#!/usr/bin/env python3
"""Mercado Pago FALSO para pruebas locales. Responde con la forma que ESPERAMOS de la API real
(no verificada contra MP real). Control: POST /__set  {"pre": {id: {...}}, "cuota": {id: {...}}}, POST /__falla {"on": true}"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
ST = {"pre": {}, "cuota": {}, "falla": False, "llamadas": []}
TOKEN = "TEST-TOKEN"
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/__llamadas": return self._j(200, ST["llamadas"])
        if self.headers.get("Authorization") != "Bearer " + TOKEN: return self._j(401, {"message": "unauthorized"})
        ST["llamadas"].append(self.path)
        if ST["falla"]: return self._j(500, {"message": "boom"})
        for pref, key in (("/preapproval/", "pre"), ("/authorized_payments/", "cuota")):
            if self.path.startswith(pref):
                i = self.path[len(pref):]
                return self._j(200, ST[key][i]) if i in ST[key] else self._j(404, {"message": "not found"})
        self._j(404, {"message": "no"})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); d = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/__set":
            for k in ("pre", "cuota"): ST[k].update(d.get(k, {}))
            if d.get("reset"): ST["pre"].clear(); ST["cuota"].clear(); ST["llamadas"].clear()
            return self._j(200, {"ok": True})
        if self.path == "/__falla": ST["falla"] = bool(d.get("on")); return self._j(200, {"ok": True})
        self._j(404, {})
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()

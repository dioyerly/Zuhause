import json, hmac, hashlib, subprocess, urllib.request, urllib.error, http.cookiejar, re, time, datetime, sys
BASE = "http://127.0.0.1:8791"; MP = "http://127.0.0.1:8792"; SECRET = "secreto-de-prueba-123"
ROOT = __file__.rsplit("/tests/", 1)[0]
OK = 0; BAD = 0
def check(nombre, cond, extra=""):
    global OK, BAD
    if cond: OK += 1
    else: BAD += 1; print("  FALLA:", nombre, extra)
def resumen(titulo):
    print(f"{titulo}: {OK} ok, {BAD} fallas"); return BAD == 0
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedir)
    def req(self, method, path, data=None, headers=None, raw=None, base=BASE):
        h = dict(headers or {}); body = None
        if raw is not None: body = raw
        elif data is not None:
            if isinstance(data, dict) and h.pop("_form", None): body = urllib.parse.urlencode(data).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
            else: body = json.dumps(data).encode(); h.setdefault("Content-Type", "application/json")
        r = urllib.request.Request(base + path, data=body, method=method, headers=h)
        try: resp = self.op.open(r, timeout=30)
        except urllib.error.HTTPError as e: resp = e
        txt = resp.read().decode("utf-8", "replace")
        try: j = json.loads(txt)
        except Exception: j = None
        return resp.status if hasattr(resp, "status") else resp.code, j, txt, resp.headers
    def api(self, action, data=None, method=None):
        m = method or ("POST" if data is not None else "GET")
        s, j, t, h = self.req(m, "/api.php?action=" + action, data, {"X-Requested-With": "fetch"})
        return s, j
    def form(self, path, campos):
        return self.req("POST", path, campos, {"_form": "1"})
import urllib.parse
def csrf_de(html):
    m = re.search(r'name="csrf" value="([a-f0-9]+)"', html); return m.group(1) if m else ""
def firmar(data_id, req_id="req-1", ts=None, secret=SECRET, minus=False):
    ts = ts or str(int(time.time() * 1000))
    mf = f"id:{data_id.lower() if minus else data_id};request-id:{req_id};ts:{ts};"
    return {"x-signature": f"ts={ts},v1=" + hmac.new(secret.encode(), mf.encode(), hashlib.sha256).hexdigest(), "x-request-id": req_id}
def webhook(topic, data_id, firma=True, **kw):
    c = Client(); h = firmar(data_id, **kw) if firma else {}
    body = {"action": "updated", "type": topic, "data": {"id": data_id}}
    return c.req("POST", f"/webhook.php?data.id={urllib.parse.quote(data_id)}&type={topic}", body, h)
def sql(q):
    r = subprocess.run(["mariadb", "-N", "-B", "nc_saas", "-e", q], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    return [l.split("\t") for l in r.stdout.splitlines()]
def sql1(q):
    r = sql(q); return r[0][0] if r else None
def mp_set(pre=None, cuota=None, reset=False):
    Client().req("POST", "/__set", {"pre": pre or {}, "cuota": cuota or {}, "reset": reset}, base=MP)
def mp_falla(on): Client().req("POST", "/__falla", {"on": on}, base=MP)
def mp_llamadas(): return Client().req("GET", "/__llamadas", base=MP)[1]
def local(dias=0, horas=0):
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=3) + datetime.timedelta(days=dias, hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
def iso(dias=0):
    return (datetime.datetime.utcnow() + datetime.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S.000-00:00")
def pre(id, estado="authorized", email="ana@ejemplo.com", monto=4000, prox_dias=30):
    return {id: {"id": id, "payer_id": 123, "payer_email": email, "status": estado, "reason": "Zuhause mensual", "external_reference": "",
        "date_created": iso(0), "last_modified": iso(0), "next_payment_date": iso(prox_dias),
        "auto_recurring": {"frequency": 1, "frequency_type": "months", "transaction_amount": monto, "currency_id": "ARS"}}}
def cuota(id, pre_id, estado="processed", pago="approved", monto=4000, retry=0, dias=0):
    return {id: {"id": id, "preapproval_id": pre_id, "status": estado, "transaction_amount": monto, "currency_id": "ARS", "retry_attempt": retry,
        "debit_date": iso(dias), "date_created": iso(dias), "payment": {"id": 999, "status": pago, "status_detail": "accredited" if pago == "approved" else "cc_rejected_insufficient_amount"}}}
def mail_log():
    try: return open(ROOT + "/storage/mail.log", encoding="utf-8").read()
    except FileNotFoundError: return ""

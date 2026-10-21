from lib import *
import lib
PID = "2c9380849f8a1b2c019f8a1b2c0d0001"
mp_set(reset=True)

print("== Webhook: seguridad")
s, j, t, h = Client().req("GET", "/webhook.php"); check("GET no permitido", s == 405)
s, *_ = webhook("subscription_preapproval", PID, firma=False); check("sin firma 401", s == 401)
s, *_ = webhook("subscription_preapproval", PID, secret="otro-secreto"); check("firma con otro secreto 401", s == 401)
f = firmar(PID); f["x-signature"] = f["x-signature"][:-3] + "000"
s, *_ = Client().req("POST", f"/webhook.php?data.id={PID}&type=subscription_preapproval", {"data": {"id": PID}}, f); check("firma alterada 401", s == 401)
f = firmar(PID)  # firma de un id, pedido con otro id => no debe pasar
s, *_ = Client().req("POST", "/webhook.php?data.id=OTROID&type=subscription_preapproval", {}, f); check("firma de otro id 401", s == 401)
check("firmas inválidas registradas", int(sql1("select count(*) from eventos_mp where resultado='firma_invalida'")) >= 4)
check("con firma inválida no se llamó a MP", mp_llamadas() == [])
mp_set(reset=True)
s, *_ = webhook("subscription_preapproval", "AbC123XyZ", minus=True); check("firma armada con id en minúscula también válida", s == 200)
mp_set(reset=True)
s, j, *_ = webhook("subscription_preapproval", "../../etc/passwd"); check("id con ../ no pasa (firma de ese id)", s == 200 and mp_llamadas() == [])
s, *_ = webhook("subscription_preapproval", "123456"); check("id desconocido en MP => 200 ignorado (prueba del panel)", s == 200)
s, *_ = webhook("payment", "55"); check("tema no manejado => 200", s == 200)
check("no se creó nada con ids basura", sql1("select count(*) from suscripciones") == "0")

print("== Webhook: suscripción nueva")
mp_set(pre=pre(PID, "authorized"))
s, *_ = webhook("subscription_preapproval", PID); check("webhook preapproval 200", s == 200)
check("suscripción guardada", sql1(f"select estado from suscripciones where preapproval_id='{PID}'") == "authorized")
check("monto en centavos", sql1(f"select monto_cent from suscripciones where preapproval_id='{PID}'") == "400000")
check("email del pagador", sql1(f"select payer_email from suscripciones where preapproval_id='{PID}'") == "ana@ejemplo.com")
ml = mail_log(); check("mail de alta enviado", "alta.php?pid=" + PID in ml and "para: ana@ejemplo.com" in ml)
webhook("subscription_preapproval", PID); webhook("subscription_preapproval", PID)
check("repetir el webhook no duplica ni reenvía mail", mail_log().count("alta.php?pid=" + PID) == 1 and sql1("select count(*) from suscripciones") == "1")

print("== Webhook: MP caído => reintento")
mp_falla(True); s, *_ = webhook("subscription_preapproval", PID); mp_falla(False)
check("MP caído => 500 para que MP reintente", s == 500)
check("queda registrado el error", int(sql1("select count(*) from eventos_mp where resultado='error'")) >= 1)

print("== Alta de credenciales")
c = Client()
s, j, t, h = c.req("GET", "/alta.php"); check("sin pid pide revisar el correo", s == 200 and "Revisá tu correo" in t)
s, j, t, h = c.req("GET", "/alta.php?pid=" + "x" * 90); check("pid inválido no consulta MP", "Revisá tu correo" in t)
s, j, t, h = c.req("GET", "/alta.php?pid=noexiste123"); check("pid inexistente", "No encontramos" in t)
s, j, t, h = c.req("GET", "/alta.php?preapproval_id=" + PID); check("acepta preapproval_id (back_url de MP)", "Creá tu acceso" in t and 'readonly' in t)
check("CSP en página de alta", "default-src 'none'" in h.get("Content-Security-Policy", ""))
tok = csrf_de(t)
base = {"csrf": tok, "pid": PID, "nombre": "Ana Pérez", "email": "ana@ejemplo.com", "clave": "Clave-Segura-2026", "clave2": "Clave-Segura-2026"}
s, j, t2, h = c.form("/alta.php", {**base, "csrf": "mal"}); check("sin CSRF válido no crea", "venció" in t2 and sql1("select count(*) from cuentas") == "0")
s, j, t2, h = c.form("/alta.php", {**base, "clave": "corta", "clave2": "corta"}); check("clave corta rechazada", "al menos 10" in t2 and sql1("select count(*) from cuentas") == "0")
s, j, t2, h = c.form("/alta.php", {**base, "clave2": "Otra-Clave-2026"}); check("claves distintas rechazadas", "no coinciden" in t2)
s, j, t2, h = c.form("/alta.php", {**base, "clave": "aaaaaaaaaaaa", "clave2": "aaaaaaaaaaaa"}); check("clave repetitiva rechazada", "menos obvia" in t2)
s, j, t2, h = c.form("/alta.php", {**base, "nombre": ""}); check("nombre obligatorio", "nombre" in t2.lower() and sql1("select count(*) from cuentas") == "0")
s, j, t2, h = c.form("/alta.php", {**base, "email": "otro@evil.com", "nombre": "<b>Ana</b>"}); 
check("alta OK", "Tu cuenta quedó creada" in t2, t2[:200])
check("el email queda fijado al del pago (ignora el enviado)", sql1("select email from cuentas") == "ana@ejemplo.com")
check("la suscripción quedó vinculada", sql1(f"select cuenta_id is not null from suscripciones where preapproval_id='{PID}'") == "1")
check("clave guardada con hash", sql1("select pass_hash like '$2y$%' or pass_hash like '$argon%' from cuentas") == "1" and "Clave-Segura" not in sql1("select pass_hash from cuentas"))
check("mail de cuenta creada", "Tu cuenta de Zuhause está lista" in mail_log())
s, j, t2, h = c.form("/alta.php", base); check("repetir el alta no crea otra cuenta", sql1("select count(*) from cuentas") == "1" and "ya está creado" in t2)
s, j, t2, h = Client().req("GET", "/alta.php?pid=" + PID); check("link de alta usado muestra 'ya creado'", "ya está creado" in t2)

print("== Alta: pago no confirmado / dos claims")
P2 = "2c9380849f8a1b2c019f8a1b2c0d0002"
mp_set(pre=pre(P2, "pending", "bea@ejemplo.com"))
s, j, t, h = Client().req("GET", "/alta.php?pid=" + P2); check("pending => espera confirmación, sin formulario", "Esperando" in t and "<form" not in t)
mp_set(pre=pre(P2, "cancelled", "bea@ejemplo.com"))
s, j, t, h = Client().req("GET", "/alta.php?pid=" + P2); check("cancelled => no deja crear cuenta", "Esperando" in t and sql1("select count(*) from cuentas") == "1")
mp_falla(True); s, j, t, h = Client().req("GET", "/alta.php?pid=" + P2); mp_falla(False)
check("MP caído => mensaje amable, sin formulario", "verificando" in t and "<form" not in t)
# carrera: dos navegadores con el mismo link
mp_set(pre=pre(P2, "authorized", "bea@ejemplo.com"))
a, b = Client(), Client()
ta = csrf_de(a.req("GET", "/alta.php?pid=" + P2)[2]); tb = csrf_de(b.req("GET", "/alta.php?pid=" + P2)[2])
f2 = {"pid": P2, "nombre": "Bea", "clave": "Clave-Segura-2026", "clave2": "Clave-Segura-2026"}
ra = a.form("/alta.php", {**f2, "csrf": ta}); rb = b.form("/alta.php", {**f2, "csrf": tb})
check("dos altas con el mismo link => una sola cuenta", sql1("select count(*) from cuentas where email='bea@ejemplo.com'") == "1")
# email que ya tiene cuenta con otra suscripción
P3 = "2c9380849f8a1b2c019f8a1b2c0d0003"
mp_set(pre=pre(P3, "authorized", ""))   # MP no informa email
c3 = Client(); t3 = c3.req("GET", "/alta.php?pid=" + P3)[2]
check("sin email de MP => se pide el email", "readonly" not in t3 and 'name="email"' in t3)
r = c3.form("/alta.php", {"csrf": csrf_de(t3), "pid": P3, "nombre": "X", "email": "ana@ejemplo.com", "clave": "Clave-Segura-2026", "clave2": "Clave-Segura-2026"})
check("email ya registrado rechazado", "ya tiene una cuenta" in r[2] and sql1("select count(*) from cuentas where email='ana@ejemplo.com'") == "1")
r = c3.form("/alta.php", {"csrf": csrf_de(r[2]), "pid": P3, "nombre": "X", "email": "nuevo@ejemplo.com'; DROP TABLE cuentas;--", "clave": "Clave-Segura-2026", "clave2": "Clave-Segura-2026"})
check("email inválido/inyección rechazado", "email válido" in r[2] and sql1("select count(*) from cuentas") == "2")

print("== Login")
c = Client()
s, j = c.api("load"); check("load sin sesión => 401", s == 401)
s, j, t, h = Client().req("POST", "/api.php?action=login", {"email": "ana@ejemplo.com", "password": "x"}, {}); check("sin header fetch => 400", s == 400)
s, j = c.api("login", {"email": "ana@ejemplo.com", "password": "mala"}); check("clave mala 401", s == 401 and j["error"] == "Email o clave incorrectos")
s, j2 = c.api("login", {"email": "nadie@ejemplo.com", "password": "mala"}); check("email inexistente: mismo mensaje (no revela cuentas)", s == 401 and j2 == j)
s, j = c.api("login", {"email": "ana@ejemplo.com' OR '1'='1", "password": "x"}); check("inyección SQL en login => 401", s == 401)
s, j = c.api("login", {"email": "ana@ejemplo.com"}); check("login sin clave => 401", s == 401)
s, j = c.api("login", {"email": "ANA@Ejemplo.com ", "password": "Clave-Segura-2026"}); check("login OK (email normalizado)", s == 200 and j["ok"])
cookie = [x for x in c.jar if x.name == "nc_sess"][0]; check("cookie HttpOnly", cookie.has_nonstandard_attr("HttpOnly") or "HttpOnly" in str(cookie._rest))
s, j = c.api("load"); check("load OK", s == 200 and j["acceso"] == "activo" and j["cuenta"]["email"] == "ana@ejemplo.com" and j["data"] is None and j["version"] == 0)
check("load incluye link para reactivar", j["reactivar_url"].startswith("https://"))

print("== Guardar / versiones / respaldos")
d = {"version": 1, "setupDone": True, "settings": {"family": {"name": "Pérez"}}, "expenses": []}
s, j = c.api("save", {"version": 0, "data": d}); check("primer guardado v1", s == 200 and j["version"] == 1)
s, j = c.api("save", {"version": 0, "data": d}); check("versión vieja => 409", s == 409)
s, j = c.api("save", {"version": 1, "data": {**d, "x": "ñandú ✓"}}); check("guardado v2", s == 200 and j["version"] == 2)
s, j = c.api("load"); check("datos vuelven intactos (UTF-8)", j["data"]["x"] == "ñandú ✓" and j["version"] == 2)
s, j = c.api("save", {"version": 2}); check("sin datos => 400", s == 400)
s, j = c.api("save", {"version": 2, "data": "texto"}); check("datos no objeto => 400", s == 400)
s, j, t, h = c.req("GET", "/api.php?action=save", None, {"X-Requested-With": "fetch"}); check("save por GET => 405", s == 405)
v = 2
for i in range(35):
    s, j = c.api("save", {"version": v, "data": {**d, "n": i}}); v = j["version"]
check("respaldos limitados a 30", sql1("select count(*) from casa_respaldos where cuenta_id=1") == "30")
big = {"version": 1, "pad": "x" * (16 * 1024 * 1024)}
s, j = c.api("save", {"version": v, "data": big}); check("más de 15 MB => 413", s == 413)
check("no se rompió el estado", c.api("load")[1]["version"] == v)

print("== Aislamiento entre cuentas")
mp_set(pre=pre("2c9380849f8a1b2c019f8a1b2c0d0004", "authorized", "carla@ejemplo.com"))
webhook("subscription_preapproval", "2c9380849f8a1b2c019f8a1b2c0d0004")
cc = Client(); t4 = cc.req("GET", "/alta.php?pid=2c9380849f8a1b2c019f8a1b2c0d0004")[2]
cc.form("/alta.php", {"csrf": csrf_de(t4), "pid": "2c9380849f8a1b2c019f8a1b2c0d0004", "nombre": "Carla", "clave": "Otra-Clave-Larga-1", "clave2": "Otra-Clave-Larga-1"})
cc.api("login", {"email": "carla@ejemplo.com", "password": "Otra-Clave-Larga-1"})
j = cc.api("load")[1]; check("Carla no ve los datos de Ana", j["data"] is None and j["version"] == 0)
s, j = cc.api("save", {"version": 0, "data": {"version": 1, "mia": 1}}); check("Carla guarda lo suyo", s == 200 and j["version"] == 1)
check("Ana sigue con lo suyo", c.api("load")[1]["data"].get("mia") is None)
import concurrent.futures as cf
vv = c.api("load")[1]["version"]
def g(i):
    k = Client(); k.api("login", {"email": "ana@ejemplo.com", "password": "Clave-Segura-2026"}); return k.api("save", {"version": vv, "data": {"version": 1, "p": i}})[0]
with cf.ThreadPoolExecutor(8) as ex: rs = list(ex.map(g, range(8)))
check("8 guardados simultáneos con la misma versión => solo uno gana", rs.count(200) == 1 and rs.count(409) == 7, str(rs))
s, j = c.api("logout", {}); check("logout", s == 200); check("después de logout => 401", c.api("load")[0] == 401)
raise SystemExit(0 if resumen("t1_flujo") else 1)

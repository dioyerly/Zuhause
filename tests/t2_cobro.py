from lib import *
mp_set(reset=True)
CL = "Clave-Segura-2026"
def crear(pid, email, nombre="Cliente"):
    mp_set(pre=pre(pid, "authorized", email)); webhook("subscription_preapproval", pid)
    c = Client(); t = c.req("GET", "/alta.php?pid=" + pid)[2]
    c.form("/alta.php", {"csrf": csrf_de(t), "pid": pid, "nombre": nombre, "clave": CL, "clave2": CL})
    u = Client(); s, j = u.api("login", {"email": email, "password": CL}); assert s == 200, (s, j); return u
def cid(email): return sql1(f"select id from cuentas where email='{email}'")
def acceso(u): s, j = u.api("load"); return s, (j or {}).get("acceso")

print("== Estados de pago -> acceso")
P = "aa000000000000000000000000000001"; u = crear(P, "ana@t.ar", "Ana")
check("recién suscripta: activo (cobro inicial en curso)", acceso(u) == (200, "activo"))
mp_set(cuota=cuota("q1", P, "processed", "approved"))
s, *_ = webhook("subscription_authorized_payment", "q1"); check("webhook de cuota 200", s == 200)
check("pago guardado en centavos y procesado", sql(f"select estado, monto_cent from pagos where mp_id='q1'") == [["processed", "400000"]])
check("sigue activo", acceso(u) == (200, "activo"))
webhook("subscription_authorized_payment", "q1"); check("cuota repetida no duplica", sql1("select count(*) from pagos") == "1")
# pago aprobado aunque el estado de la cuota diga otra cosa
mp_set(cuota=cuota("q9", P, "scheduled", "approved")); webhook("subscription_authorized_payment", "q9")
check("payment.approved => procesado", sql1("select estado from pagos where mp_id='q9'") == "processed"); sql("delete from pagos where mp_id='q9'")

# falla de cobro: MP reintenta, cuota 'recycling'
mp_set(cuota=cuota("q2", P, "recycling", "rejected", retry=2)); webhook("subscription_authorized_payment", "q2")
check("cuota fallida registrada con reintento", sql(f"select estado, reintento from pagos where mp_id='q2'") == [["recycling", "2"]])
check("un reintento fallido no corta el acceso si el último pago es reciente", acceso(u) == (200, "activo"))
# envejecer: último pago hace 40 días, próximo cobro vencido
sql(f"update pagos set fecha_debito='{local(-40)}' where mp_id='q1'"); sql(f"update suscripciones set proximo_cobro='{local(-10)}' where preapproval_id='{P}'")
sql(f"update pagos set fecha_debito='{local(-1)}', estado='recycling' where mp_id='q2'")
check("sin pagos hace 40 días y cobro vencido => SOLO LECTURA", acceso(u) == (200, "solo_lectura"))
s, j = u.api("load"); check("en solo lectura sigue viendo sus datos", j["data"] is None or isinstance(j["data"], dict))
s, j = u.api("save", {"version": 0, "data": {"version": 1}}); check("en solo lectura NO puede guardar (402)", s == 402 and "suscripción" in j["error"])
check("nada se guardó", sql1(f"select count(*) from casa_estado where cuenta_id={cid('ana@t.ar')}") == "0")
sql(f"update pagos set fecha_debito='{local(-32)}' where mp_id='q1'")
check("dentro de la gracia (32 días) sigue activo", acceso(u) == (200, "activo"))
sql(f"update pagos set fecha_debito='{local(-36)}' where mp_id='q1'")
check("pasada la gracia (36 días) solo lectura", acceso(u) == (200, "solo_lectura"))
mp_set(cuota=cuota("q3", P, "processed", "approved")); webhook("subscription_authorized_payment", "q3")
check("entra un pago nuevo => vuelve a ACTIVO", acceso(u) == (200, "activo"))
s, j = u.api("save", {"version": 0, "data": {"version": 1, "ok": 1}}); check("y puede guardar de nuevo", s == 200)

print("== Cancelación / pausa")
sql(f"update pagos set fecha_debito='{local(-10)}' where mp_id in ('q1','q3')")
mp_set(pre=pre(P, "cancelled", "ana@t.ar")); webhook("subscription_preapproval", P)
check("estado cancelled guardado", sql1(f"select estado from suscripciones where preapproval_id='{P}'") == "cancelled")
check("cancelada pero con período pagado vigente => sigue activo", acceso(u) == (200, "activo"))
check("cancelación auditada", sql1("select count(*) from auditoria where accion='suscripcion_cancelled'") == "1")
sql(f"update pagos set fecha_debito='{local(-40)}' where mp_id in ('q1','q3')")
check("cancelada y período vencido => solo lectura", acceso(u) == (200, "solo_lectura"))
mp_set(pre=pre(P, "paused", "ana@t.ar")); webhook("subscription_preapproval", P)
check("pausada y vencida => solo lectura", acceso(u) == (200, "solo_lectura"))

print("== Re-suscripción con el mismo email")
mails0 = mail_log().count("alta.php?pid=")
P2 = "aa000000000000000000000000000002"
mp_set(pre=pre(P2, "authorized", "ana@t.ar")); webhook("subscription_preapproval", P2)
check("la nueva suscripción se vincula sola a la cuenta existente", sql1(f"select cuenta_id from suscripciones where preapproval_id='{P2}'") == cid("ana@t.ar"))
check("no manda mail de alta (ya tiene cuenta)", mail_log().count("alta.php?pid=") == mails0)
check("vuelve a tener acceso activo", acceso(u) == (200, "activo"))

print("== Orden invertido: llega la cuota antes que la suscripción")
P3 = "aa000000000000000000000000000003"
mp_set(pre=pre(P3, "authorized", "bea@t.ar"), cuota=cuota("q30", P3))
s, *_ = webhook("subscription_authorized_payment", "q30")
check("cuota sin suscripción previa: crea ambas", s == 200 and sql1(f"select count(*) from suscripciones where preapproval_id='{P3}'") == "1" and sql1("select count(*) from pagos where mp_id='q30'") == "1")
mp_set(cuota=cuota("q31", "../x"))
check("cuota con preapproval_id raro => no rompe (500 reintentable, nada guardado)", webhook("subscription_authorized_payment", "q31")[0] == 500 and sql1("select count(*) from pagos where mp_id='q31'") == "0")

print("== Override del dueño")
P4 = "aa000000000000000000000000000004"; v = crear(P4, "carla@t.ar", "Carla")
sql(f"update cuentas set override='bloqueado', session_ver=session_ver+1 where email='carla@t.ar'")
check("bloqueada: la sesión abierta cae (401)", v.api("load")[0] == 401)
v2 = Client(); check("bloqueada: puede loguear pero load => 403", v2.api("login", {"email": "carla@t.ar", "password": CL})[0] == 200 and v2.api("load")[0] == 403)
s, j = v2.api("save", {"version": 0, "data": {"version": 1}}); check("bloqueada no guarda (403)", s == 403)
sql("update cuentas set override='activo' where email='carla@t.ar'"); sql(f"update suscripciones set estado='cancelled' where preapproval_id='{P4}'")
check("cortesía: activo aunque la suscripción esté cancelada", acceso(v2) == (200, "activo"))
sql("update cuentas set override='auto' where email='carla@t.ar'"); sql(f"update suscripciones set creada='{local(-60)}' where preapproval_id='{P4}'")
check("vuelve a automático => por estado", acceso(v2) == (200, "solo_lectura"))

print("== Cuenta borrada / sesión inválida")
sql("update cuentas set session_ver=session_ver+1 where email='ana@t.ar'")
check("cambiar session_ver invalida sesiones", u.api("load")[0] == 401)

print("== Recuperar clave")
c = Client(); t = c.req("GET", "/recuperar.php")[2]; tk = csrf_de(t)
r1 = c.form("/recuperar.php", {"csrf": tk, "email": "ana@t.ar"})[2]; r2 = c.form("/recuperar.php", {"csrf": tk, "email": "noexiste@t.ar"})[2]
check("misma respuesta exista o no el email", "Si ese email tiene una cuenta" in r1 and r1 == r2)
ml = mail_log(); m = re.findall(r"recuperar\.php\?t=([a-f0-9]{64})", ml); check("mail con link de un solo uso", len(m) == 1 and "noexiste@t.ar" not in ml)
tok = m[0]; check("en la base se guarda el hash, no el token", tok not in sql1("select group_concat(token_hash) from recuperaciones") and sql1("select count(*) from recuperaciones") == "1")
s, j, t, h = Client().req("GET", "/recuperar.php?t=" + "0" * 64); check("token inventado => vencido", "Link vencido" in t)
s, j, t, h = Client().req("GET", "/recuperar.php?t=abc"); check("token malformado => vencido", "Link vencido" in t)
r = Client(); t = r.req("GET", "/recuperar.php?t=" + tok)[2]; check("token válido muestra formulario", "Elegí una clave nueva" in t)
x = r.form("/recuperar.php", {"csrf": csrf_de(t), "t": tok, "clave": "corta", "clave2": "corta"})[2]; check("clave corta rechazada", "al menos 10" in x)
x = r.form("/recuperar.php", {"csrf": "mal", "t": tok, "clave": "Nueva-Clave-2026", "clave2": "Nueva-Clave-2026"})[2]; check("sin CSRF no cambia", "venció" in x)
x = r.form("/recuperar.php", {"csrf": csrf_de(t), "t": tok, "clave": "Nueva-Clave-2026", "clave2": "Nueva-Clave-2026"})[2]; check("clave cambiada", "Clave cambiada" in x)
check("clave vieja ya no entra", Client().api("login", {"email": "ana@t.ar", "password": CL})[0] == 401)
check("clave nueva entra", Client().api("login", {"email": "ana@t.ar", "password": "Nueva-Clave-2026"})[0] == 200)
x = Client().req("GET", "/recuperar.php?t=" + tok)[2]; check("el token no se puede reusar", "Link vencido" in x)
c2 = Client(); tk2 = csrf_de(c2.req("GET", "/recuperar.php")[2]); c2.form("/recuperar.php", {"csrf": tk2, "email": "bea@t.ar"}); tok2 = re.findall(r"t=([a-f0-9]{64})", mail_log())[-1]
sql(f"update recuperaciones set expira='{local(-1)}' where token_hash=sha2('{tok2}',256)"); check("token vencido por tiempo", "Link vencido" in Client().req("GET", "/recuperar.php?t=" + tok2)[2])
n0 = len(re.findall(r"recuperar\.php\?t=", mail_log()))
for i in range(6): c2.form("/recuperar.php", {"csrf": tk2, "email": "bea@t.ar"})
check("límite de pedidos de recuperación (3 por hora por email)", len(re.findall(r"recuperar\.php\?t=", mail_log())) - n0 <= 2)

print("== Freno de login")
w = Client()
codes = [w.api("login", {"email": "carla@t.ar", "password": "mal"})[0] for _ in range(7)]
check("5 fallos y luego 429", codes[:5] == [401] * 5 and codes[5] == 429 and codes[6] == 429, str(codes))
check("incluso con la clave correcta sigue bloqueado", w.api("login", {"email": "carla@t.ar", "password": CL})[0] == 429)
check("otro email no se ve afectado", Client().api("login", {"email": "bea@t.ar", "password": "mal"})[0] == 401)
sql("delete from login_intentos"); check("pasado el freno vuelve a funcionar", Client().api("login", {"email": "carla@t.ar", "password": CL})[0] == 200)
raise SystemExit(0 if resumen("t2_cobro") else 1)

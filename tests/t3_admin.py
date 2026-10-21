from lib import *
import subprocess, json as J
mp_set(reset=True)
CL = "Clave-Segura-2026"; AD = "Admin-Clave-Larga-2026"
def crear(pid, email, nombre):
    mp_set(pre=pre(pid, "authorized", email)); webhook("subscription_preapproval", pid)
    c = Client(); t = c.req("GET", "/alta.php?pid=" + pid)[2]
    c.form("/alta.php", {"csrf": csrf_de(t), "pid": pid, "nombre": nombre, "clave": CL, "clave2": CL})
    u = Client(); u.api("login", {"email": email, "password": CL}); return u
P1, P2, P3 = "bb000000000000000000000000000001", "bb000000000000000000000000000002", "bb000000000000000000000000000003"
u1 = crear(P1, "ana@t.ar", "<script>alert(1)</script>Ana"); u2 = crear(P2, "bea@t.ar", "Bea")
mp_set(cuota=cuota("c1", P1, "processed", "approved", dias=-20)); webhook("subscription_authorized_payment", "c1")
mp_set(cuota=cuota("c2", P1, "processed", "approved", dias=-1)); webhook("subscription_authorized_payment", "c2")
mp_set(cuota=cuota("c3", P2, "recycling", "rejected", retry=1)); webhook("subscription_authorized_payment", "c3")
mp_set(pre=pre(P3, "authorized", "pago-sin-alta@t.ar")); webhook("subscription_preapproval", P3)   # pagó, no creó cuenta
mp_set(pre=pre(P2, "cancelled", "bea@t.ar")); webhook("subscription_preapproval", P2)
u1.api("save", {"version": 0, "data": {"version": 1, "notaSecreta": "GASTO-PRIVADO-XYZ"}})

print("== Panel: acceso")
a = Client()
for p in ("/admin.php",):
    s, j, t, h = a.req("GET", p); check("sin login muestra formulario", s == 200 and "Panel del dueño" in t and "ana@t.ar" not in t)
tk = csrf_de(t)
r = a.form("/admin.php", {"csrf": tk, "email": "dueno@test.ar", "clave": "mala"}); check("clave mala rechazada", "Datos incorrectos" in r[2] and "ana@t.ar" not in r[2])
r = a.form("/admin.php", {"csrf": "x", "email": "dueno@test.ar", "clave": AD}); check("sin CSRF no entra aunque la clave sea correcta", "venció" in r[2])
r = a.form("/admin.php", {"csrf": tk, "email": "otro@t.ar", "clave": AD}); check("otro email con la clave correcta no entra", "Datos incorrectos" in r[2])
r = a.form("/admin.php", {"csrf": tk, "email": "ana@t.ar", "clave": CL}); check("un cliente no entra al panel con su clave", "Datos incorrectos" in r[2])
check("un cliente logueado en la app no ve el panel", "Panel del dueño" in u1.req("GET", "/admin.php")[2])
r = a.form("/admin.php", {"csrf": tk, "email": "dueno@test.ar", "clave": AD}); check("login correcto redirige", r[0] == 302 or "Clientes" in r[2])
s, j, t, h = a.req("GET", "/admin.php"); check("panel visible", s == 200 and "Clientes" in t)
check("lista cliente y email", "ana@t.ar" in t and "bea@t.ar" in t)
check("XSS escapado en el nombre", "<script>alert(1)</script>" not in t and "&lt;script&gt;" in t)
check("NO muestra datos privados de la casa", "GASTO-PRIVADO-XYZ" not in t)
check("muestra al que pagó y no creó acceso", "pago-sin-alta@t.ar" in t and "Pagaron pero no crearon" in t)
check("muestra pagos y la cuota fallida", "recycling" in t and "processed" in t)
check("muestra notificaciones de MP y firma", "subscription_preapproval" in t)
check("CSP restrictiva y noindex", "default-src 'none'" in h.get("Content-Security-Policy", "") and "noindex" in t)
check("ingreso mensual calculado ($ 4.000,00)", "4.000,00" in t)

print("== Panel: acciones")
tk = csrf_de(t); cu1 = sql1("select id from cuentas where email='ana@t.ar'")
r = a.form("/admin.php", {"a": "override", "cuenta": cu1, "valor": "bloqueado"}); check("acción sin CSRF rechazada", "venció" in r[2] and sql1("select override from cuentas where id=" + cu1) == "auto")
r = a.form("/admin.php", {"csrf": tk, "a": "override", "cuenta": cu1, "valor": "hackeado"}); check("valor inválido ignorado", sql1("select override from cuentas where id=" + cu1) == "auto")
r = a.form("/admin.php", {"csrf": tk, "a": "override", "cuenta": cu1, "valor": "bloqueado"}); check("bloquear cliente", sql1("select override from cuentas where id=" + cu1) == "bloqueado")
check("el cliente bloqueado cae al instante", u1.api("load")[0] == 401)
check("acción auditada", sql1("select count(*) from auditoria where accion='admin_override'") == "1")
a.form("/admin.php", {"csrf": tk, "a": "override", "cuenta": cu1, "valor": "auto"}); check("volver a automático", sql1("select override from cuentas where id=" + cu1) == "auto")
r = a.form("/admin.php", {"csrf": tk, "a": "link_clave", "cuenta": cu1}); m = re.search(r"recuperar\.php\?t=([a-f0-9]{64})", r[2])
check("genera link de clave de un solo uso", bool(m))
check("el link sirve", "Elegí una clave nueva" in Client().req("GET", "/recuperar.php?t=" + m.group(1))[2])
r = a.form("/admin.php", {"csrf": tk, "a": "resync", "pre": P2}); check("sincronizar con MP", "Sincronizada" in r[2])
r = a.form("/admin.php", {"csrf": tk, "a": "resync", "pre": "../x"}); check("resync con id raro => error controlado", "No se pudo sincronizar" in r[2])

print("== Descarga para el Centro de operaciones")
s, j, t, h = a.req("GET", "/admin.php?descargar=centro"); check("descarga JSON", s == 200 and isinstance(j, list) and "attachment" in h.get("Content-Disposition", ""))
tipos = [e["type"] for e in j]; check("tiene alta, renovación, fallo, cancelación y usuarios", {"subscription_started", "renewal", "payment_failed", "cancellation", "users"} <= set(tipos), str(tipos))
check("primer pago = alta, segundo = renovación", [e["type"] for e in j if e.get("external_id", "").startswith("nc_pay_")] == ["subscription_started", "renewal"])
check("importes en pesos (no centavos)", [e["amount"] for e in j if e["type"] == "renewal"] == [4000])
check("campos del formato del Centro", all(k in j[0] for k in ("source", "external_id", "type", "app", "date")) and j[0]["app"] == "Zuhause")
check("ids únicos (importar dos veces no duplica)", len({e["external_id"] for e in j}) == len(j))
check("fechas AAAA-MM-DD", all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date"]) for e in j))
check("sin datos privados de la casa", "GASTO-PRIVADO" not in t)
check("sin sesión no descarga", "[" not in Client().req("GET", "/admin.php?descargar=centro")[2][:5])
s, j, t, h = a.req("GET", "/admin.php?salir=1"); check("salir cierra sesión", "Panel del dueño" in a.req("GET", "/admin.php")[2] and "ana@t.ar" not in a.req("GET", "/admin.php")[2])

print("== Freno del panel")
z = Client(); tk = csrf_de(z.req("GET", "/admin.php")[2])
res = [("Datos incorrectos" in z.form("/admin.php", {"csrf": tk, "email": "dueno@test.ar", "clave": "mala%d" % i})[2]) for i in range(5)]
r = z.form("/admin.php", {"csrf": tk, "email": "dueno@test.ar", "clave": AD}); check("tras 5 fallos bloquea incluso con la clave correcta", all(res) and "Demasiados intentos" in r[2])
sql("delete from login_intentos")

print("== export.php (token)")
H = {"Authorization": "Bearer tok_export_0123456789abcdef0123456789abcdef"}
s, j, t, h = Client().req("GET", "/export.php", None, H); check("con token => eventos", s == 200 and isinstance(j["events"], list) and len(j["events"]) > 3)
check("CORS no se abre sin origen permitido", "Access-Control-Allow-Origin" not in h)
s, j, t, h = Client().req("GET", "/export.php", None, {**H, "Origin": "http://centro.local"}); check("CORS para el origen configurado", h.get("Access-Control-Allow-Origin") == "http://centro.local")
s, j, t, h = Client().req("GET", "/export.php", None, {**H, "Origin": "http://malo.com"}); check("CORS no para otros orígenes", "Access-Control-Allow-Origin" not in h)
check("preflight OPTIONS => 204", Client().req("OPTIONS", "/export.php", None, {"Origin": "http://centro.local"})[0] == 204)
check("sin token 401", Client().req("GET", "/export.php")[0] == 401)
check("token en query string no vale", Client().req("GET", "/export.php?token=tok_export_0123456789abcdef0123456789abcdef")[0] == 401)
s, j, *_ = Client().req("GET", "/export.php?desde=2999-01-01", None, H); check("filtro desde", s == 200 and all(e["date"] >= "2999-01-01" for e in j["events"]))
codes = [Client().req("GET", "/export.php", None, {"Authorization": "Bearer mal"})[0] for _ in range(25)]
check("tras muchos intentos malos => 429", 429 in codes)
check("y con el token correcto también (bloqueo temporal)", Client().req("GET", "/export.php", None, H)[0] == 429)
sql("delete from login_intentos")

print("== Reglas de acceso (unitarias)")
php = r'''<?php require "%s/lib/core.php";
$n=strtotime("2026-10-21 12:00:00"); $d=86400; $f=fn($t)=>date("Y-m-d H:i:s",$t);
$S=fn($e,$extra=[])=>array_merge(["estado"=>$e,"periodo_dias"=>30,"creada"=>$f($n-100*$d),"proximo_cobro"=>null],$extra);
$C=["override"=>"auto"]; $r=[];
$r[]=calcular_acceso(["override"=>"bloqueado"],$S("authorized"),$f($n),$n,5)["acceso"];                    // bloqueado
$r[]=calcular_acceso(["override"=>"activo"],null,null,$n,5)["acceso"];                                      // activo
$r[]=calcular_acceso($C,null,null,$n,5)["acceso"];                                                          // solo_lectura
$r[]=calcular_acceso($C,$S("authorized"),$f($n-10*$d),$n,5)["acceso"];                                      // activo
$r[]=calcular_acceso($C,$S("authorized"),$f($n-35*$d+60),$n,5)["acceso"];                                   // activo (justo en la gracia)
$r[]=calcular_acceso($C,$S("authorized"),$f($n-35*$d-60),$n,5)["acceso"];                                   // solo_lectura
$r[]=calcular_acceso($C,$S("authorized",["proximo_cobro"=>$f($n+3*$d)]),$f($n-60*$d),$n,5)["acceso"];      // activo (MP sigue programando)
$r[]=calcular_acceso($C,$S("authorized",["creada"=>$f($n-2*$d)]),null,$n,5)["acceso"];                      // activo (primer cobro en curso)
$r[]=calcular_acceso($C,$S("authorized",["creada"=>$f($n-9*$d)]),null,$n,5)["acceso"];                      // solo_lectura (nunca pagó)
$r[]=calcular_acceso($C,$S("cancelled"),$f($n-10*$d),$n,5)["acceso"];                                       // activo (período pagado)
$r[]=calcular_acceso($C,$S("cancelled"),$f($n-31*$d),$n,5)["acceso"];                                       // solo_lectura
$r[]=calcular_acceso($C,$S("paused"),$f($n-29*$d),$n,5)["acceso"];                                          // activo
$r[]=calcular_acceso($C,$S("pending"),null,$n,5)["acceso"];                                                 // solo_lectura (creada hace 100 días)
$r[]=calcular_acceso($C,$S("authorized",["periodo_dias"=>360]),$f($n-300*$d),$n,5)["acceso"];               // activo (plan anual)
echo implode(",",$r);''' % ROOT
r = subprocess.run(["php", "-r", php[5:]], capture_output=True, text=True).stdout
esp = "bloqueado,activo,solo_lectura,activo,activo,solo_lectura,activo,activo,solo_lectura,activo,solo_lectura,activo,solo_lectura,activo"
check("14 casos de calcular_acceso", r == esp, r)
raise SystemExit(0 if resumen("t3_admin") else 1)

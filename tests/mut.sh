#!/bin/bash
# Mutaciones: rompe a propósito una regla de seguridad/cobro y exige que alguna prueba falle.
cd "$(dirname "$0")"; ROOT="$(cd .. && pwd)"; N=0; MAT=0
m() { # archivo | python-regex | reemplazo | descripción
  f="$ROOT/$1"; cp "$f" /tmp/mut.bak
  python3 - "$f" "$2" "$3" <<'PY' || { echo "  (patrón no encontrado) $4"; cp /tmp/mut.bak "$f"; return; }
import sys,re
p,pat,rep=sys.argv[1:4]; s=open(p).read(); n=s.replace(pat,rep,1)
if n==s: sys.exit(1)
open(p,'w').write(n)
PY
  N=$((N+1)); ok=1
  for s in t1_flujo.py t2_cobro.py t3_admin.py; do ./run.sh $s > /tmp/mut.out 2>&1 || { ok=0; break; }; done
  cp /tmp/mut.bak "$f"
  if [ $ok = 0 ]; then MAT=$((MAT+1)); echo "  MATADA  $4  ($(grep -m1 FALLA /tmp/mut.out | cut -c1-90))"; else echo "  SOBREVIVIÓ  $4"; fi
}
m lib/mp.php 'hash_equals(hash_hmac('"'"'sha256'"'"', $manifest, $secret), strtolower($v1))' 'true' "firma siempre válida"
m webhook.php 'if (!$firma) {' 'if (false) {' "webhook sin chequear firma"
m api.php "if (\$acc['acceso'] !== 'activo') out(402" "if (false) out(402" "guardar sin estar activo"
m api.php "|| (int)\$cuenta['session_ver'] !== (int)(\$_SESSION['sv'] ?? -1)" "" "sesiones no se invalidan"
m lib/core.php '$g = $gracia * 86400;' '$g = 0;' "sin período de gracia"
m alta.php 'if ($q->fetchColumn() !== null) {' 'if (false) {' "alta repetida permitida"
m recuperar.php 'r.usado = 0 AND r.expira > ?' 'r.expira > ?' "token reutilizable"
m lib/core.php '>= $max;' '>= 9999;' "sin freno de intentos"
m lib/core.php 'return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, '"'"'UTF-8'"'"');' 'return $s;' "sin escapar HTML"
m export.php 'if (!hash_equals($tokenCfg, $dado)) {' 'if (false) {' "export sin token"
m lib/mp.php "if ((\$pago['status'] ?? '') === 'approved') \$estado = 'processed';" "" "pago aprobado no cuenta"
m api.php "WHERE cuenta_id = ? FOR UPDATE" "WHERE cuenta_id = ?" "sin bloqueo al guardar"
m api.php "if ((int)\$cur !== \$clientVersion) {" "if (false) {" "sin control de versión"
m admin.php "if (!csrf_ok()) { \$aviso" "if (false) { \$aviso" "panel sin CSRF"
m lib/core.php "if (\$estado === 'authorized') {" "if (false) {" "authorized no da acceso"
m alta.php "\$email = \$sub['payer_email'] !== '' ? \$sub['payer_email'] : normalizar_email((string)(\$_POST['email'] ?? ''));" "\$email = normalizar_email((string)(\$_POST['email'] ?? ''));" "email del alta no fijado al pagador"
echo "Mutaciones matadas: $MAT de $N"

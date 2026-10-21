# Zuhause · versión con suscripción (Mercado Pago)

Cada cliente paga una suscripción, crea su usuario y su clave, y tiene **su propia casa** aislada de las demás.
Si deja de pagar, pasa a **solo lectura** (ve y descarga sus datos, no puede modificarlos). Vos ves clientes y pagos en `admin.php`.

## Qué hace cada archivo

| Archivo | Para qué |
|---|---|
| `index.html` + `assets/` | Landing con el botón **Suscribirme**, capturas reales de la app y botón de WhatsApp. Editás 3 líneas al final del archivo: link de Mercado Pago, número de WhatsApp y mensaje |
| `app.html` | La aplicación (pantalla de ingreso con email + clave) |
| `alta.php` | A donde vuelve el cliente después de pagar: verifica el pago con Mercado Pago y le deja crear su clave |
| `recuperar.php` | "Olvidé mi clave" (link de un solo uso por mail, vence en 1 hora) |
| `webhook.php` | Recibe los avisos de Mercado Pago (alta, pagos, cancelación) |
| `api.php` | Guarda y carga los datos de cada casa; corta el guardado si no hay pago |
| `admin.php` | **Tu panel**: clientes, estado de pago, cuotas, avisos de MP, auditoría |
| `export.php` | Entrega las métricas al Centro de operaciones (con token) |
| `schema.sql` | Tablas (importar una sola vez) |
| `config.example.php` | Copiar como `config.php` y completar |

## Puesta en marcha en Hostinger

1. **Base de datos**: en hPanel creá una base MySQL (nombre, usuario, clave). En phpMyAdmin importá `schema.sql`.
2. **Subir archivos**: todo el contenido de la carpeta a `public_html` (o al subdominio). Activá SSL/HTTPS.
3. **Configuración**: copiá `config.example.php` a `config.php` y completá:
   - `DB_DSN`, `DB_USER`, `DB_PASS` (los de tu base), `APP_URL` (tu dominio con https, sin barra final).
   - `ADMIN_EMAIL` y `ADMIN_PASSWORD_HASH`: generá el hash con `php -r "echo password_hash('TU-CLAVE-LARGA', PASSWORD_DEFAULT);"` (o en un sitio local que ejecute PHP). Usá una clave larga y única.
   - `EXPORT_TOKEN`: `php -r "echo bin2hex(random_bytes(24));"`.
   - `MAIL_FROM`: un remitente de tu dominio (crealo en Hostinger > Correos) para que los mails no caigan en spam.
4. **Mercado Pago** (ver abajo) y completar `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `SUSCRIBIRME_URL`.
5. Editá las 3 líneas del final de `index.html` (link de suscripción, número de WhatsApp con código de país, mensaje). El precio mostrado ($32.000 tachado y $10.999) está escrito en el texto de la página: si cambia, se edita ahí y en el plan de Mercado Pago. **El monto que se cobra lo define el plan que creás en Mercado Pago: tiene que ser $10.999.**
6. **Probá todo en modo prueba antes de cobrar** (lista al final).

## Mercado Pago: lo que tenés que configurar vos

1. Creá una aplicación en *Tus integraciones* y copiá el **Access Token** a `MP_ACCESS_TOKEN`.
2. Creá el **plan de suscripción** (monto y frecuencia). En `back_url` del plan poné `https://TU-DOMINIO/alta.php`.
3. En *Webhooks* configurá la URL `https://TU-DOMINIO/webhook.php`, eventos de **Planes y suscripciones** (suscripción y pagos recurrentes), y copiá la **clave secreta** a `MP_WEBHOOK_SECRET`.
4. El link de pago del plan va en `SUSCRIBIRME_URL` (config) y en `index.html`.

El cobro lo hace Mercado Pago. Este sistema solo **recibe los avisos y decide el acceso**. Nunca confía en lo que dice el aviso: usa solo el ID y le pregunta a la API de Mercado Pago el estado real.

## Prueba gratis

La landing, la pantalla de alta y el ingreso mencionan **3 días gratis**. La prueba la configurás vos en el plan de Mercado Pago; este sistema no la calcula. Durante la prueba la suscripción figura como `authorized` y el cliente tiene acceso. Si cancela durante la prueba, antes de que haya un primer pago, pasa a solo lectura de inmediato.

## Cómo se decide quién entra

* Suscripción **autorizada**: acceso completo, mientras Mercado Pago siga programando cobros o el último pago esté dentro de su período + `GRACIA_DIAS` (5 por defecto).
* **Cobro fallido**: Mercado Pago reintenta; durante la gracia sigue con acceso. Pasada la gracia → solo lectura. A las 3 cuotas rechazadas Mercado Pago cancela solo.
* **Cancelada o pausada**: conserva el acceso hasta el fin del período que ya pagó; después, solo lectura.
* **Volvió a pagar** (aunque sea con una suscripción nueva con el mismo email): se reactiva sola.
* En `admin.php` podés poner a cualquier cliente en **Cortesía** (acceso gratis) o **Bloqueado** (corta ya).
* Tus clientes nunca pierden sus datos por dejar de pagar: pueden verlos y descargar el respaldo.

## Centro de operaciones

* En el Centro registrá una app llamada exactamente **Zuhause** (el nombre tiene que coincidir).
* Manual: en `admin.php` → **Descargar para Centro de operaciones** → en el Centro, *Importar eventos JSON*. Los IDs son estables: importar dos veces no duplica.
* Automático: `export.php` con `Authorization: Bearer EXPORT_TOKEN` devuelve `{"events":[...]}` en el mismo formato. El Centro hoy es una página estática: para que lo lea solo hay que agregarle un botón "Sincronizar" que haga ese pedido (no está hecho). `EXPORT_ORIGIN` debe ser exactamente el origen desde donde abrís el Centro.

## Seguridad: qué está y qué no

Está: claves con hash, freno de intentos en la base (por email y por IP), sesiones que se invalidan al cambiar la clave o bloquear, cookies HttpOnly + SameSite=Strict, protección CSRF, recuperación con token de un solo uso guardado como hash, webhook con firma HMAC, panel con sesión aparte y auditoría, mensajes que no revelan qué emails existen, cada casa aislada por cuenta.

**No está** (decidilo antes de vender): segundo factor (2FA), cifrado de los datos en la base, política de privacidad y términos y condiciones (necesarios por la ley de datos personales), mails transaccionales con SPF/DKIM configurados (los configurás en Hostinger/DNS), copias de seguridad externas de la base (activá las de Hostinger).

## Lista de pruebas con Mercado Pago (obligatoria antes de cobrar)

Las pruebas automáticas usan un Mercado Pago **simulado** con la forma de respuesta que esperamos. Falta confirmarlo contra el real:

- [ ] Suscribirte con una cuenta de prueba: ¿vuelve a `alta.php` con `preapproval_id` en la URL? (si no, igual llega el mail con el link).
- [ ] En *Notificaciones de Mercado Pago* del panel: ¿aparece `subscription_preapproval` con **Firma: ok**? Si dice "no", la fórmula de la firma difiere de la esperada (`id:…;request-id:…;ts:…;`): hay que ajustar `mp_firma_valida` en `lib/mp.php`.
- [ ] ¿`payer_email` viene completo? Si viene vacío, el cliente escribe su email al crear la cuenta (ya contemplado).
- [ ] Un pago aprobado: ¿aparece en *Pagos (cuotas)* como `processed`?
- [ ] Un pago rechazado de prueba: ¿aparece como `recycling` y el cliente conserva acceso durante la gracia?
- [ ] Cancelar desde Mercado Pago: ¿el panel muestra `cancelled` y el cliente conserva el acceso hasta fin de período?
- [ ] Botón **Sincronizar con MP** en el panel: repara cualquier estado que se haya perdido.

## Pruebas automáticas (carpeta `tests/`, no subir a producción)

`tests/run.sh t1_flujo.py` (y `t2_cobro.py`, `t3_admin.py`) levantan MariaDB de prueba, un Mercado Pago falso y PHP, y corren los chequeos. `tests/mut.sh` rompe reglas a propósito para comprobar que las pruebas las detectan.

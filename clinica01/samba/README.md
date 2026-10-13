# Samba AD DC en clinica01

Identidad centralizada del kit (R10, D-05). El dominio `ad.salud.movil` lo usan el recurso SMB, Grafana y la consulta de formularios. Lo instala y configura el rol `samba_ad` de [`../../ansible/`](../../ansible/) con `playbooks/samba.yml`. Los nombres, grupos, usuarios y la política están en `ansible/inventarios/kit/group_vars/all/samba.yml` y las contraseñas en el vault.

| Elemento | Valor |
|---|---|
| Paquetes | `samba-ad-dc`, `samba-ad-provision`, `samba`, `winbind` y `smbclient` 2:4.19.5+dfsg-4ubuntu9.8, `krb5-user` 1.20.1-6ubuntu2.10, retenidos con `hold` (versiones en `paquetes.yml`). `smbd`, `nmbd` y `winbind` quedan enmascarados, porque en un DC los reemplaza `samba-ad-dc` |
| Dominio | Realm `AD.SALUD.MOVIL`, dominio NetBIOS `SALUD`, DC `DC01` (`dc01.ad.salud.movil`). El hostname de la VM sigue siendo `clinica01` |
| DNS | DNS interno de Samba (`SAMBA_INTERNAL`) para `ad.salud.movil`. Lo demás lo reenvía a BIND9 en kit01 (`10.20.20.10` y `::10`). clinica01 resuelve por BIND9, que delega la subzona `ad` a este DC |
| Escucha | Solo `lo`, `10.20.20.11` y `fd5a:fc7e:d716:20::11` (`bind interfaces only`). El 53 de systemd-resolved (`127.0.0.53` y `127.0.0.54`) no se toca |
| Firewall (ufw) | `53/udp` y `53/tcp` solo desde kit01 (`10.20.20.1`, `.10`, `::1` y `::10`), para la delegación (F-25). Los demás puertos del DC los abre la tarea que los usa (445 en platform#9, 636 en observability#2) |
| Grupos | `clinicos` y `admins` |
| Usuarios de prueba | `ana.rojas` y `carlos.perez` en `clinicos`, `laura.gomez` en `admins` |
| Política de contraseñas | Sin complejidad, longitud mínima 8, historial de 5, sin vencimiento y bloqueo de 15 minutos después de 5 intentos fallidos. Las contraseñas son las académicas del grupo (R-14) |
| Log de autenticación | `/var/log/samba/auth.log` (`auth_audit:3`), con los intentos fallidos y exitosos de Kerberos, NTLM y LDAP. Rotación semanal en `/etc/logrotate.d/samba-auth` |
| Datos | `/var/lib/samba/` (base del dominio y `sysvol`) |

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/samba.yml    # Samba AD DC en clinica01
ansible-playbook playbooks/dns.yml      # delegación de ad.salud.movil en BIND9
```

- **Instalación.** Los paquetes se instalan con un `policy-rc.d` temporal que impide arrancar `smbd`, `nmbd` y `winbind`, así que nunca corren con la configuración de fábrica.
- **Aprovisionamiento.** Solo si no existe `/var/lib/samba/private/sam.ldb`. Antes se guarda el `smb.conf` de fábrica como `smb.conf.ubuntu`. Después el rol escribe su propio `smb.conf` (validado con `testparm`) y `krb5.conf`.
- **Contraseña de Administrator.** La política de fábrica rechaza la contraseña del vault, así que el dominio se aprovisiona con una temporal que genera Samba y nunca se guarda. Después de aplicar la política, el rol prueba la clave del vault con `kinit` y la fija con `samba-tool user setpassword` si no funciona. Ese primer `kinit` queda en el log como un intento fallido de `Administrator`.
- **Usuarios.** La contraseña solo se pone al crear el usuario. Cambiarla en el vault no cambia la de un usuario que ya existe.
- **Idempotencia.** La política se compara con `samba-tool domain passwordsettings show` y los grupos, usuarios y miembros con sus listados, así que una segunda ejecución termina con `changed=0`.

Para agregar un usuario o un grupo se edita `samba.yml` y se vuelve a ejecutar el playbook.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `systemctl is-active samba-ad-dc` | `active` |
| `sudo ss -tulnp \| grep samba` | Solo en `127.0.0.1`, `::1`, `10.20.20.11` y `fd5a:fc7e:d716:20::11` |
| Desde la Interna, `host -t SRV _ldap._tcp.ad.salud.movil` (o en kit01 `dig -b 10.20.10.1 @10.20.20.10 SRV _ldap._tcp.ad.salud.movil` y `dig -b fd5a:fc7e:d716:10::1 @fd5a:fc7e:d716:20::10 ...`) | `0 100 389 dc01.ad.salud.movil.` |
| `dig @10.20.20.10 AAAA dc01.ad.salud.movil` | `fd5a:fc7e:d716:20::11` |
| En clinica01, `kinit ana.rojas@AD.SALUD.MOVIL` y `klist` | Ticket `krbtgt/AD.SALUD.MOVIL@AD.SALUD.MOVIL` |
| `sudo samba-tool group listmembers clinicos` | `ana.rojas` y `carlos.perez` |
| `sudo samba-tool domain passwordsettings show` | Los valores de `samba_politica` |
| Una clave errada (`kinit` o `smbclient -L //10.20.20.11 -U usuario%x`) y `sudo grep WRONG_PASSWORD /var/log/samba/auth.log` | Una línea por intento, con `remote host [ipv4:...]` o `[ipv6:...]` |

Para probar Kerberos por una sola familia se usa un `krb5.conf` temporal con `KRB5_CONFIG`, con `kdc = 10.20.20.11` o `kdc = [fd5a:fc7e:d716:20::11]` dentro del bloque del realm.

## Diagnóstico

- **No arranca.** `systemctl status samba-ad-dc` y `sudo journalctl -u samba-ad-dc`. Si cambió `smb.conf`, `testparm -s`.
- **`host -t SRV` da `NXDOMAIN` o `SERVFAIL` desde los clientes.** Desde kit01, `dig @10.20.20.11 SOA ad.salud.movil`. Si no responde, revisar ufw en clinica01 (`sudo ufw status`) y el servicio. Si responde, revisar la delegación en BIND9 (`kit01/bind9/README.md`).
- **`kinit: Cannot find KDC`.** El nombre `dc01.ad.salud.movil` no resuelve. Revisar `/etc/hosts` y el `krb5.conf`.
- **`kinit: Clock skew too great`.** La hora de clinica01 no está sincronizada (`chronyc tracking`).
- **Usuario bloqueado.** `badPwdCount` y `lockoutTime` en `sudo samba-tool user show <usuario>`. Se desbloquea solo a los 15 minutos o con `sudo samba-tool user unlock <usuario>`.

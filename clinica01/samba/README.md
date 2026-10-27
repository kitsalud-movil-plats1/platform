# Samba AD DC y recursos SMB en clinica01

Identidad centralizada del kit (R10, D-05) y almacenamiento compartido (R9). El dominio `ad.salud.movil` lo usan los recursos SMB `archivos` y `contenido`, Grafana y la consulta de formularios. Lo instala y configura el rol `samba_ad` de [`../../ansible/`](../../ansible/) con `playbooks/samba.yml`. Los nombres, grupos, usuarios, recursos y la política están en `ansible/inventarios/kit/group_vars/all/samba.yml` y las contraseñas en el vault.

| Elemento | Valor |
|---|---|
| Paquetes | `samba-ad-dc`, `samba-ad-provision`, `samba`, `winbind` y `smbclient` 2:4.19.5+dfsg-4ubuntu9.8, `krb5-user` 1.20.1-6ubuntu2.10, retenidos con `hold` (versiones en `paquetes.yml`). `smbd`, `nmbd` y `winbind` quedan enmascarados, porque en un DC los reemplaza `samba-ad-dc` |
| Dominio | Realm `AD.SALUD.MOVIL`, dominio NetBIOS `SALUD`, DC `DC01` (`dc01.ad.salud.movil`). El hostname de la VM sigue siendo `clinica01` |
| DNS | DNS interno de Samba (`SAMBA_INTERNAL`) para `ad.salud.movil`. Lo demás lo reenvía a BIND9 en kit01 (`10.20.20.10` y `::10`). clinica01 resuelve por BIND9, que delega la subzona `ad` a este DC |
| Escucha | Solo `lo`, `10.20.20.11` y `fd5a:fc7e:d716:20::11` (`bind interfaces only`). El 53 de systemd-resolved (`127.0.0.53` y `127.0.0.54`) no se toca |
| Firewall (ufw) | `53/udp` y `53/tcp` solo desde kit01 (`10.20.20.1`, `.10`, `::1` y `::10`), para la delegación (F-25). `445/tcp` solo desde la Interna (`10.20.10.0/24` y `fd5a:fc7e:d716:10::/64`, F-05). `636/tcp` solo desde kit01, para el login LDAPS de Grafana (F-13) |
| Grupos | `clinicos` (gid 10001) y `admins` (gid 10002) |
| Usuarios de prueba | `ana.rojas` (uid 10101) y `carlos.perez` (10102) en `clinicos`, `laura.gomez` (10103) en `admins` |
| IDs POSIX | Fijos con los atributos RFC2307 (`gidNumber` y `uidNumber`), que el DC usa por `idmap_ldb:use rfc2307`. Así los dueños de los archivos son los mismos si el dominio se reconstruye y se restaura un backup (P11) |
| Recursos SMB | `\\archivos.salud.movil\archivos` en `/srv/samba/archivos`, solo para `clinicos`, con cifrado obligatorio. `\\archivos.salud.movil\contenido` en `/srv/samba/contenido` (`zim/`, `salud/` y `comunidad/`), con escritura para `clinicos` y `admins` y cifrado deseado |
| LDAPS | En el 636, con un certificado de `dc01.ad.salud.movil` que firma el intermedio de clinica01 de la CA del kit (rol `ca_interna`, `ca_hojas_vm` en `host_vars/clinica01.yml`). La llave se genera en la VM. `smb.conf` apunta a `/etc/kitsalud/tls/dc01.ad.key`, a `dc01.ad.crt` (hoja e intermedio) y a `raiz.crt`. Se renueva con Ansible 30 días antes de vencer y Samba se reinicia solo. El certificado que Samba genera solo no trae subjectAltName y los clientes en Go, como Grafana, no lo aceptan |
| Protocolo | SMB3 como mínimo en todo el DC (`server min protocol = SMB3`), así que SMB1 y SMB2 se rechazan |
| Kerberos | SPN `cifs/archivos.salud.movil` en la cuenta `DC01$`. Un usuario con ticket entra sin contraseña; los equipos fuera del dominio usan NTLMv2 |
| Política de contraseñas | Sin complejidad, longitud mínima 8, historial de 5, sin vencimiento y bloqueo de 15 minutos después de 5 intentos fallidos. Las contraseñas son las académicas del grupo (R-14) |
| Log de autenticación | `/var/log/samba/auth.log` (`auth_audit:3`), con los intentos fallidos y exitosos de Kerberos, NTLM y LDAP. Rotación semanal en `/etc/logrotate.d/samba-auth` |
| Datos | `/var/lib/samba/` (base del dominio y `sysvol`) y `/srv/samba/` (recursos, en el disco de datos de 120 GB) |

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/clinica01.yml   # antes, el certificado LDAPS de dc01.ad (rol ca_interna)
ansible-playbook playbooks/samba.yml       # Samba AD DC en clinica01
ansible-playbook playbooks/dns.yml         # delegación de ad.salud.movil en BIND9
```

El rol se detiene con un aviso si todavía no existe `/etc/kitsalud/tls/dc01.ad.crt`.

- **Instalación.** Los paquetes se instalan con un `policy-rc.d` temporal que impide arrancar `smbd`, `nmbd` y `winbind`, así que nunca corren con la configuración de fábrica.
- **Aprovisionamiento.** Solo si no existe `/var/lib/samba/private/sam.ldb`. Antes se guarda el `smb.conf` de fábrica como `smb.conf.ubuntu`. Después el rol escribe su propio `smb.conf` (validado con `testparm`) y `krb5.conf`.
- **Contraseña de Administrator.** La política de fábrica rechaza la contraseña del vault, así que el dominio se aprovisiona con una temporal que genera Samba y nunca se guarda. Después de aplicar la política, el rol prueba la clave del vault con `kinit` y la fija con `samba-tool user setpassword` si no funciona. Ese primer `kinit` queda en el log como un intento fallido de `Administrator`.
- **Usuarios.** La contraseña solo se pone al crear el usuario. Cambiarla en el vault no cambia la de un usuario que ya existe.
- **Idempotencia.** La política se compara con `samba-tool domain passwordsettings show` y los grupos, usuarios y miembros con sus listados, así que una segunda ejecución termina con `changed=0`.

- **IDs.** El `gidNumber` y el `uidNumber` se agregan con `samba-tool group addunixattrs` y `user addunixattrs` solo si faltan, y después se vacía la caché de winbind (`net cache flush`). Cambiar un número en `samba.yml` no cambia uno que ya existe.
- **Recursos.** Cada carpeta es de `root` y del primer grupo del recurso, con modo `2770` y una ACL POSIX (normal y por defecto) con `rwx` para cada grupo del recurso. Los recursos no usan ACL de Windows (`nt acl support = no`, sin `acl_xattr`), así que el kernel aplica el setgid y la ACL por defecto, y todo lo que se crea queda del grupo del recurso con `rw` para sus grupos (`create mask = 0660`, `directory mask = 2770`). Los permisos se cambian en `samba.yml`, no desde el Explorador de Windows.

Para agregar un usuario, un grupo o un recurso se edita `samba.yml` y se vuelve a ejecutar el playbook. El primer grupo de un usuario es su grupo POSIX principal.

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

**Recursos SMB.** `smbclient` lee la contraseña de la variable `PASSWD`. Cada prueba se repite con `-I 10.20.20.11` y con `-I fd5a:fc7e:d716:20::11`.

| Comando | Resultado esperado |
|---|---|
| `smbclient //archivos.salud.movil/archivos -U 'SALUD\ana.rojas' -c 'put /etc/hostname prueba.txt; get prueba.txt /tmp/p.txt'` | `putting file` y `getting file` |
| `smbclient //archivos.salud.movil/archivos -U 'SALUD\laura.gomez' -c ls` | `tree connect failed: NT_STATUS_ACCESS_DENIED` (no está en `clinicos`) |
| `laura.gomez` crea un archivo en `contenido/salud` y `ana.rojas` lo sobrescribe | Las dos escrituras funcionan |
| `ls -ln /srv/samba/archivos` y `getfacl -n` de un archivo nuevo | Grupo `10001`, modo `rw-rw----` y `group:10002:rwx` en los de `contenido` |
| `smbclient ... -m NT1 -c ls` y `-m SMB2` | `NT_STATUS_INVALID_PARAMETER_MIX` y `NT_STATUS_NOT_SUPPORTED` |
| Una sesión abierta con `--client-protection=off` y `sudo smbstatus -S` | `SMB3_11` y `AES-128-GCM` en `archivos`, aunque el cliente no pida cifrado |
| `kinit ana.rojas@AD.SALUD.MOVIL`, `smbclient //archivos.salud.movil/archivos --use-kerberos=required -N -c ls </dev/null` y `klist` | Lista el recurso y aparece el ticket `cifs/archivos.salud.movil@AD.SALUD.MOVIL` |
| `sudo ufw status \| grep 445` | Solo `10.20.10.0/24` y `fd5a:fc7e:d716:10::/64` |

Desde la Interna, en Linux `smbclient //archivos.salud.movil/archivos -U 'SALUD\ana.rojas'` o `sudo mount -t cifs //archivos.salud.movil/archivos /mnt -o username=ana.rojas,domain=SALUD,vers=3.1.1,seal`, y en Windows `\\archivos.salud.movil\archivos` con el usuario `SALUD\ana.rojas`. Desde la Comunidad el 445 no responde y kit01 lo registra con `fw-drop IN=br-com ... DPT=445`.

Para probar Kerberos por una sola familia se usa un `krb5.conf` temporal con `KRB5_CONFIG`, con `kdc = 10.20.20.11` o `kdc = [fd5a:fc7e:d716:20::11]` dentro del bloque del realm.

## Diagnóstico

- **No arranca.** `systemctl status samba-ad-dc` y `sudo journalctl -u samba-ad-dc`. Si cambió `smb.conf`, `testparm -s`.
- **`host -t SRV` da `NXDOMAIN` o `SERVFAIL` desde los clientes.** Desde kit01, `dig @10.20.20.11 SOA ad.salud.movil`. Si no responde, revisar ufw en clinica01 (`sudo ufw status`) y el servicio. Si responde, revisar la delegación en BIND9 (`kit01/bind9/README.md`).
- **`kinit: Cannot find KDC`.** El nombre `dc01.ad.salud.movil` no resuelve. Revisar `/etc/hosts` y el `krb5.conf`.
- **`kinit: Clock skew too great`.** La hora de clinica01 no está sincronizada (`chronyc tracking`).
- **`NT_STATUS_ACCESS_DENIED` con un usuario que sí está en el grupo.** `wbinfo --user-groups=<usuario>` tiene que incluir el gid del grupo. Si falta, `sudo net cache flush` y repetir.
- **Archivos nuevos con grupo `100` y entradas `user:<uid>` en la ACL.** Es la herencia de ACL de Windows de `acl_xattr`. El recurso tiene que tener `nt acl support = no` y `vfs objects = dfs_samba4` (`testparm -s --section-name=archivos`).
- **El 445 no responde desde la Interna.** En kit01, `sudo nft list chain inet filtro forward | grep 445` (el contador sube con cada conexión) y `journalctl -k | grep fw-drop`; en clinica01, `sudo ufw status`.
- **`smbclient --use-kerberos=required` se queda esperando.** Pide contraseña aunque use el ticket; se agrega `-N`.
- **Usuario bloqueado.** `badPwdCount` y `lockoutTime` en `sudo samba-tool user show <usuario>`. Se desbloquea solo a los 15 minutos o con `sudo samba-tool user unlock <usuario>`.

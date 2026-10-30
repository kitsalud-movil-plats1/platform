# Backups del kit con restic

kit01 extrae una vez por semana los datos y las configuraciones de cada VM por SSH, los junta en un área temporal y los guarda cifrados con restic en el disco USB, que solo se monta durante la copia (R11, D-10, sección 10.6). Las VMs no tienen la clave del repositorio ni llaves hacia kit01. Lo instalan el rol `backups` (kit01) y el rol `backup_origen` (VMs) de [`../ansible/`](../ansible/) con `playbooks/backups.yml`.

| Snapshot (etiqueta) | Qué tiene | De dónde sale |
|---|---|---|
| `config` | `/etc` de kit01 (con la raíz de la CA en `/etc/kitsalud/ca` y los certificados de `/etc/kitsalud/tls`), `/etc` y `/srv` de las dos VMs sin datos grandes (Compose, `.env`, archivos de DHIS2, datos de Caddy con el intermedio de cada VM, configuración de Jellyfin) | kit01 directo; VMs por rsync |
| `recursos` | Recursos SMB `archivos` y `contenido` de clinica01, con dueños numéricos, ACL y atributos extendidos | rsync |
| `bd` | `pg_dump -Fc` de `dhis2` y `prerregistro`, y los roles (`pg_dumpall --globals-only`) | comando forzado `postgres` |
| `dominio` | `samba-tool domain backup offline` de `ad.salud.movil` (`.tar.bz2`) | comando forzado `dominio` |

No se respaldan las imágenes de las VMs (se reconstruyen con Ansible), los datos crudos de PostgreSQL (van por `pg_dump`) ni los medios de comunidad01 (son una copia de `contenido` o los descarga Ansible).

| Elemento | Valor |
|---|---|
| Disco | Seagate de 500 GB por USB 3.0, GPT con una partición ext4 `kitbackup`. Se monta por UUID (`backup_disco_uuid`) en `/mnt/backup` con `noatime,nodev,nosuid,noexec` y solo durante la copia. No está en `fstab`. Datos del disco en `workspace/contexto/equipos/disco-usb-backups.md` |
| Repositorio | `/mnt/backup/restic`. Si el disco no lo tiene, el script lo crea (`restic init`) en la primera copia, así que basta con conectarlo. Si existe pero no abre con la clave, no lo toca |
| Clave | `/etc/kitsalud/backup/restic.clave` (`400` root), desde `vault_restic_password` |
| Frecuencia | `backup.timer`, el domingo a las 4:00 (después de la analítica de DHIS2 de las 2:00). Con `Persistent=true`, si kit01 estaba apagado corre al arrancar y espera hasta 10 min a que respondan las VMs |
| Retención | 4 semanales y 3 mensuales por etiqueta (`restic forget --group-by host,tags --prune`), y `restic check` después |
| Área temporal | `/var/lib/kitsalud/backup/<equipo>/` (`700` root). Las copias de rsync se conservan entre pasadas, así solo se transfiere lo que cambió. Los dumps se borran después del snapshot |
| Llave | ed25519 en `/etc/kitsalud/backup/id_ed25519`, generada en kit01. Las VMs reciben solo la pública |
| `known_hosts` | `/etc/kitsalud/backup/known_hosts`, con la llave de host ed25519 de cada VM y sus dos IP (`StrictHostKeyChecking=yes`) |
| Conexión | Por IPv6 y, si no responde, por IPv4 (`direcciones` de cada equipo). El log dice cuál usó |
| Variables | Política (frecuencia, retención, usuario, llave, rutas de kit01) en `group_vars/all/backups.yml`; disco, direcciones y qué se extrae de cada equipo en `group_vars/all/backups-equipos.yml` (el laboratorio virtual tiene el suyo) |

**Qué puede hacer la llave en las VMs.** Entra como el usuario `backup` de Ubuntu, sin contraseña, solo con la llave y solo desde las direcciones de kit01 en `br-srv` (`from=`, F-02). sshd le fuerza `sudo -n /usr/local/sbin/backup-extraer`, sin PTY, túneles ni reenvíos, y sudo solo le permite ese comando sin argumentos. El comando lee la orden de `SSH_ORIGINAL_COMMAND` y solo acepta `ping`, `rsync --server --daemon .` con los módulos de `/etc/kitsalud/backup/rsyncd.conf` (solo lectura, sin listar, con `--remove-source-files` rechazado), y en clinica01 `postgres <base>` para las bases de la lista, `postgres-globales` y `dominio`. Cualquier otra orden termina con `Orden no permitida` y queda en el log de autenticación.

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/backups.yml                    # kit01, VMs y timer
ansible-playbook playbooks/backups.yml --skip-tags timer  # todo menos activar el timer
```

La primera jugada prepara kit01 (restic retenido, clave, llave, `known_hosts`, script y unidades), la segunda las VMs y la tercera activa el timer, cuando las VMs ya aceptan la llave. Una segunda ejecución termina con `changed=0`.

**Al conectar el disco** no hace falta nada más. La siguiente copia programada lo monta, crea el repositorio y hace la primera copia. Para no esperar al domingo se lanza a mano (abajo).

## Cómo se usa

```bash
sudo systemctl start backup.service    # copia ahora (por ejemplo, antes de un cambio)
journalctl -u backup -o cat            # qué extrajo, los snapshots y el espacio del disco
```

Para consultar o restaurar se monta el disco y se cargan las variables de restic:

```bash
sudo -i
mount -o noatime,nodev,nosuid,noexec UUID=<backup_disco_uuid> /mnt/backup
export RESTIC_REPOSITORY=/mnt/backup/restic RESTIC_PASSWORD_FILE=/etc/kitsalud/backup/restic.clave RESTIC_CACHE_DIR=/var/cache/restic
restic snapshots
umount /mnt/backup                     # al terminar
```

| Qué restaurar | Cómo |
|---|---|
| Un archivo de `archivos` | `restic restore latest --tag recursos --include /var/lib/kitsalud/backup/clinica01/archivos/<ruta> --target /tmp/r` y copiarlo de vuelta a `/srv/samba/archivos/` de clinica01 con `rsync -aAX` (conserva dueños y ACL) |
| Una base | `restic dump latest --tag bd /var/lib/kitsalud/backup/clinica01/postgres/<base>.dump > /tmp/<base>.dump`, copiarlo a clinica01 y `docker exec -i dhis2-db-1 pg_restore -U dhis -d <base> --clean --if-exists < /tmp/<base>.dump`. Una sola tabla con `-t <tabla>` |
| El dominio | `restic dump latest --tag dominio /var/lib/kitsalud/backup/clinica01/dominio/dominio.tar.bz2 > /tmp/dominio.tar.bz2` y en clinica01, con Samba detenido, `samba-tool domain backup restore --backup-file=/tmp/dominio.tar.bz2 --targetdir=<dir> --newservername=dc01` |
| Una configuración | `restic restore latest --tag config --include <ruta> --target /tmp/r`. Las de las VMs están bajo `/var/lib/kitsalud/backup/<equipo>/etc` o `srv` |

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `systemctl list-timers backup.timer` | La próxima copia el domingo a las 4:00 |
| `sudo systemctl start backup.service; findmnt /mnt/backup` | Termina sin error y el disco queda desmontado |
| `restic snapshots` (con el disco montado) | Un snapshot por etiqueta (`config`, `recursos`, `bd` y `dominio`) por semana |
| Sin el disco, `sudo systemctl start backup.service` | Falla con `El disco de backups (<UUID>) no está conectado`, sin tocar nada, y aparece `UnidadFallida` en **Estado del kit** |
| Desde kit01, `ssh -i /etc/kitsalud/backup/id_ed25519 backup@<vm> ping` y con `id` | `ok`; `Orden no permitida: id` |
| `rsync -e "ssh -i ..." /etc/hostname backup@[<vm>]::etc/` | `ERROR: module is read only` |
| `rsync -e "ssh -i ..." -a --remove-source-files backup@[<vm>]::etc/ /tmp/x/` | `The server is configured to refuse --remove-source-files` |
| `ssh ... backup@<vm> "postgres postgres"` | `Orden no permitida` (solo las bases de la lista) |
| En cada VM, `sudo grep -r restic /etc/kitsalud /etc/ssh/backup` | Nada; las VMs no tienen la clave del repositorio |

Cada prueba con SSH se repite con la IPv4 y la IPv6 de las dos VMs.

**Prueba sin el disco USB.** El script acepta otro disco con `BACKUP_UUID`, así que se puede probar todo con un disco de imagen y borrarlo después.

```bash
sudo truncate -s 5G /var/tmp/disco-prueba.img
L=$(sudo losetup -f --show /var/tmp/disco-prueba.img); sudo mkfs.ext4 -q -L kitprueba $L
sudo BACKUP_UUID=$(sudo blkid -s UUID -o value $L) /usr/local/sbin/backup-kit
sudo losetup -d $L; sudo rm /var/tmp/disco-prueba.img
```

## Diagnóstico

- **`backup.service` falla.** `journalctl -u backup -o cat` dice qué no se pudo extraer. Lo que falló queda fuera del snapshot de esa semana y el resto se guarda igual. En **Estado del kit** aparece `UnidadFallida` en kit01 hasta la siguiente copia correcta.
- **`El disco de backups (<UUID>) no está conectado`.** El disco no está, no enciende o es otro. `lsblk -f` debe mostrar `kitbackup` con ese UUID. Si se cambia el disco, se formatea igual y se actualiza `backup_disco_uuid`.
- **`<vm>: no responde por ...`.** La VM está apagada o el SSH desde kit01 no entra. `ssh -i /etc/kitsalud/backup/id_ed25519 backup@<ip> ping` y en la VM `journalctl -u ssh` y `ufw status`.
- **`Host key verification failed`.** Cambió la llave de host de una VM (por ejemplo, se reconstruyó). Se vuelve a ejecutar `playbooks/backups.yml`.
- **`/mnt/backup/restic existe pero restic no lo abre`.** La clave del vault no es la del repositorio. Sin la clave original el repositorio no se puede leer, así que no se borra; se recupera la clave o se usa otro disco.
- **`Failed to open .../netlogon_creds_cli.tdb` en el log.** Lo escribe `samba-tool domain backup offline` porque ese archivo es un caché con mutex. La copia del dominio se completa igual.
- **`/mnt/backup ya está montado`.** Quedó montado de una consulta manual. Se desmonta con `umount /mnt/backup`.

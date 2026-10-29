# Publicación de contenido de clinica01 a comunidad01

El personal sube el material al recurso SMB `contenido` de clinica01 y un timer lo copia a comunidad01, donde lo sirven Kiwix (`biblioteca`) y Jellyfin (`videos`). El flujo va siempre de clínica a comunidad (R9, sección 10.5, F-12). Lo instala el rol `publicacion` de [`../../ansible/`](../../ansible/) con `playbooks/publicacion.yml`, que también aplica el rol `publicacion_destino` del repositorio `apps` en comunidad01 ([`apps/comunidad01/medios/`](https://github.com/kitsalud-movil-plats1/apps/tree/main/comunidad01/medios)).

| Carpeta de `contenido` | Destino en comunidad01 | Lo sirve |
|---|---|---|
| `zim/` | `/srv/medios/zim/` (módulo `zim`) | Kiwix, después de reiniciarse solo (`kiwix-recarga.path`) |
| `salud/` | `/srv/medios/videos/salud/` (módulo `videos`) | Jellyfin, biblioteca Salud |
| `comunidad/` | `/srv/medios/videos/comunidad/` (módulo `videos`) | Jellyfin, biblioteca Comunidad |

| Elemento | Valor |
|---|---|
| Usuario | `publicacion`, local y de sistema en las dos VMs, sin contraseña. En clinica01 tiene una ACL POSIX `r-x` (normal y por defecto) en `/srv/samba/contenido` y sus carpetas, así que lee lo que sube el personal y no escribe nada |
| Llave | ed25519 en `/var/lib/publicacion/.ssh/id_ed25519`, generada en clinica01. La privada nunca sale de la VM; comunidad01 recibe solo la pública |
| `known_hosts` | Solo la llave de host ed25519 de comunidad01, con `comunidad01.salud.movil`, `10.20.20.12` y `fd5a:fc7e:d716:20::12` (`StrictHostKeyChecking=yes`) |
| Script | `/usr/local/sbin/publicar-contenido`. Dos pasadas de `rsync -rt --delete --delay-updates`, una por módulo. Los argumentos se pasan a rsync (`-n` es una prueba en seco) |
| Timer | `publicacion.timer`, 5 min después del arranque y cada 10 min desde la última corrida. `publicacion.service` corre como `publicacion` con `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp` y `NoNewPrivileges`, con prioridad baja de CPU y disco |
| Espera | Un archivo modificado hace menos de 2 min puede estar subiéndose por SMB, así que queda para la siguiente pasada (lo dice el log con `espera a la siguiente pasada`). Su versión anterior en comunidad01 tampoco se borra |
| Lo que no se publica | Ocultos (`.*`), `Thumbs.db`, `desktop.ini` y temporales de Office (`~$*`). Los enlaces simbólicos se saltan (sin `-l`) |
| ZIM de la lista | El rol descarga `contenido_zim` (`contenido.yml`) en `contenido/zim` y verifica el sha256. Anota lo que puso en `/var/lib/kitsalud/zim-del-rol.txt` y solo quita esos cuando salen de la lista; los que suba el personal no se tocan |
| Variables | `publicacion_usuario`, `publicacion_home` y `publicacion_llave` en `group_vars/all/contenido.yml`; el destino, los módulos, la frecuencia y la espera en `roles/publicacion/defaults/main.yml` |

**Qué puede hacer la llave en comunidad01.** Solo ejecutar `rsync --server --daemon` con la configuración de `/etc/kitsalud/publicacion/rsyncd.conf`, y solo desde las dos IP de clinica01. Los módulos son de solo escritura, no se listan y no dejan salir de su carpeta. El demonio protege los medios que pone el rol `jellyfin` (los de `/srv/jellyfin/medios-del-rol.txt`), así que `--delete` nunca los borra. Los detalles están en el README de `apps/comunidad01/medios/`.

## Cómo se publica

1. Subir el archivo con un usuario de `clinicos` o `admins` a `\\archivos.salud.movil\contenido`, en la carpeta que corresponda.
   - **`salud` o `comunidad`.** Video en H.264/AAC (MP4) de 480p y unos 1 Mb/s, o audio en MP3, para que Jellyfin lo reproduzca sin transcodificar (10.1). El nombre del archivo es el título que se verá. Se pueden usar subcarpetas.
   - **`zim`.** Archivos `.zim` de la biblioteca de Kiwix, directamente en la carpeta.
2. Esperar. En 12 minutos o menos queda en comunidad01. Kiwix se reinicia 30 s después y Jellyfin lo agrega a la biblioteca con su monitor de cambios.

Para quitar algo se borra del recurso, y la siguiente pasada lo borra de comunidad01. Un archivo con el mismo nombre que un medio del rol `jellyfin` no se publica (el log muestra `daemon refused to receive file`).

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/publicacion.yml                  # usuario, llave, ZIM, destino en comunidad01 y timer
ansible-playbook playbooks/publicacion.yml --skip-tags timer # todo menos activar el timer
```

El playbook tiene tres jugadas. La primera prepara clinica01 (usuario, ACL, ZIM, llave, `known_hosts`, script y unidades), la segunda prepara comunidad01 y la tercera activa el timer, cuando comunidad01 ya acepta la llave. Necesita que existan el recurso `contenido` (`playbooks/samba.yml`) y las carpetas de medios de comunidad01 (`playbooks/comunidad01.yml`). Una segunda ejecución termina con `changed=0`.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `systemctl list-timers publicacion.timer` | La próxima corrida en 10 min o menos |
| `journalctl -u publicacion` | Una línea por archivo copiado (`<f+++++++++`) o borrado (`*deleting`), y `Finished` |
| `sudo -u publicacion find /srv/samba/contenido` y `sudo -u publicacion touch /srv/samba/contenido/zim/x` | Lista el recurso; `Permission denied` al escribir |
| `sudo systemd-run --wait --pipe -p User=publicacion -p ProtectSystem=strict -p PrivateTmp=yes /usr/local/sbin/publicar-contenido -n` | Lo que copiaría y borraría, sin cambiar nada |
| Subir un video por SMB a `contenido/salud` y buscarlo como `comunidad` en `videos.salud.movil` (`/Users/<id>/Items?searchTerm=...`) | Aparece en 12 min o menos y se reproduce directo |
| `sudo -u publicacion ssh -i /var/lib/publicacion/.ssh/id_ed25519 publicacion@comunidad01.salud.movil` (y con `bash`, `-tt`, `-L` o `sftp`) | Solo el saludo `@RSYNCD: 31.0`; sin shell, sin PTY, sin túneles ni sftp |
| `sudo -u publicacion rsync -e "ssh -i ..." publicacion@comunidad01.salud.movil::videos/salud/<archivo> /tmp/` | `ERROR: module is write only` |

Cada prueba con SSH se repite con `10.20.20.12` y con `[fd5a:fc7e:d716:20::12]`.

## Diagnóstico

- **`publicacion.service` falla.** `journalctl -u publicacion` dice qué módulo y con qué código terminó rsync. En **Estado del kit** aparece `UnidadFallida` en clinica01. Se recupera sola en la siguiente pasada cuando se corrige la causa.
- **`Host key verification failed`.** Cambió la llave de host de comunidad01 (por ejemplo, la VM se reconstruyó). Se vuelve a ejecutar `playbooks/publicacion.yml`, que la lee de nuevo.
- **`Permission denied (publickey)` o `Connection timed out`.** En comunidad01, `sudo ufw status | grep publicacion` (el 22 desde las dos IP de clinica01) y `journalctl -u ssh`. La llave autorizada está en `/etc/ssh/publicacion/authorized_keys`.
- **`Falta /srv/samba/contenido/<carpeta>, no se publica`.** El disco de datos de clinica01 no está montado o el recurso no existe. El script se detiene antes de llamar a rsync para no vaciar comunidad01.
- **Un archivo no se publica.** Si el log dice `espera a la siguiente pasada`, se está subiendo o se modificó hace menos de 2 min. Si dice `daemon refused to receive file`, tiene el nombre de un medio del rol `jellyfin`. Los ocultos y los temporales de Windows no se publican.
- **El video no aparece en Jellyfin.** En comunidad01, `ls -l /srv/medios/videos/salud`. Si el archivo está, se fuerza un escaneo desde el panel de Jellyfin (Interna o NetBird) o se espera al escaneo programado.

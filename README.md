# platform

Servicios de plataforma del kit.

| Ruta | Dónde | Contenido |
|---|---|---|
| `kit01/libvirt/` | kit01 | Definiciones de las VMs `clinica01` y `comunidad01` (autostart, retardo de arranque), perfiles por misión |
| `kit01/bind9/` | kit01 | Zona `salud.movil`, zonas inversas v4/v6, delegación de `ad.salud.movil` y respuestas para la detección de portal |
| `kit01/chrony/` | kit01 | Servidor NTP (`local stratum 10`) |
| `kit01/nut/` | kit01 | NUT con `dummy-ups` y script de apagado ordenado (comunidad01 → clinica01 → kit01) |
| `kit01/netbird/` | kit01 | Instalación de NetBird para administración remota (la clave de registro no se versiona) |
| `kit01/ssh/` | kit01 | Drop-in de sshd (`PermitRootLogin no`, D-18) |
| `clinica01/samba/` | clinica01 | Aprovisionamiento de Samba AD DC (`ad.salud.movil`) y recursos SMB `archivos` y `contenido` |
| `backups/` | kit01 → disco USB | restic en modelo pull, con extracción de dumps por SSH, política de retención y restauración |
| `ansible/` | - | Inventario y playbooks (secretos en `ansible-vault`) |

El diseño de referencia está en `docs/arquitectura/00-punto-de-partida.md` (secciones 7, 11 y 14).

# platform

Servicios de plataforma del kit.

| Ruta | Dónde | Contenido |
|---|---|---|
| `kit01/libvirt/` | kit01 | VMs `clinica01` y `comunidad01` (recursos, red, discos en el LV `vms`, autostart y acceso); se crean con el rol `kit01_vms` de Ansible |
| `kit01/bind9/` | kit01 | Zona `salud.movil` e inversas v4/v6 en BIND9, autoritativo y recursivo para el kit; se despliega con el rol `bind9` de Ansible. Delegación de `ad.salud.movil` y respuestas para la detección de portal, más adelante |
| `kit01/chrony/` | kit01 | Servidor NTP (`ntp.salud.movil`) con el pool como fuente y `local stratum 10 orphan` sin Internet; se despliega con el rol `chrony` de Ansible |
| `kit01/nut/` | kit01 | NUT con `dummy-ups` y script de apagado ordenado (comunidad01 → clinica01 → kit01) |
| `kit01/netbird/` | kit01 | Instalación de NetBird para administración remota (la clave de registro no se versiona) |
| `clinica01/samba/` | clinica01 | Aprovisionamiento de Samba AD DC (`ad.salud.movil`) y recursos SMB `archivos` y `contenido` |
| `backups/` | kit01 → disco USB | restic en modelo pull, con extracción de dumps por SSH, política de retención y restauración |
| `ansible/` | - | Inventarios del kit y del laboratorio virtual, plan de direcciones, secretos en `ansible-vault`, el rol `comun` (usuario compartido, sshd sin root, zona horaria, ufw en las VMs) el rol `kit01_vms` (VMs) el rol `bind9` (DNS), el rol `chrony` (NTP) y el rol `samba_ad` (Samba AD DC y recursos SMB) |

El diseño de referencia está en `docs/arquitectura/00-punto-de-partida.md` (secciones 7, 11 y 14).

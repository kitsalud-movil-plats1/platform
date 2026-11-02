# platform

Servicios de plataforma del kit.

| Ruta | Dónde | Contenido |
|---|---|---|
| `kit01/` | kit01 | Base del hipervisor (hostname, KVM/libvirt, red `default` de libvirt detenida y NetBird retenido); se despliega con el rol `kit01_base` de Ansible |
| `kit01/libvirt/` | kit01 | VMs `clinica01` y `comunidad01` (recursos, red, discos en el LV `vms`, autostart y acceso); se crean con el rol `kit01_vms` de Ansible |
| `kit01/bind9/` | kit01 | Zona `salud.movil` e inversas v4/v6 en BIND9, autoritativo y recursivo para el kit; se despliega con el rol `bind9` de Ansible. Delegación de `ad.salud.movil` a Samba AD |
| `kit01/chrony/` | kit01 | Servidor NTP (`ntp.salud.movil`) con el pool como fuente y `local stratum 10 orphan` sin Internet; se despliega con el rol `chrony` de Ansible |
| `kit01/ca/` | kit01 → VMs | CA interna del kit: raíz en kit01, un intermedio por VM limitado a sus nombres y el certificado de `monitoreo`; se despliega con el rol `ca_interna` de Ansible |
| `kit01/nut/` | kit01 | NUT con `dummy-ups` y script de apagado ordenado (comunidad01 → clinica01 → kit01) |
| `kit01/netbird/` | kit01 | Instalación de NetBird para administración remota (la clave de registro no se versiona) |
| `clinica01/samba/` | clinica01 | Aprovisionamiento de Samba AD DC (`ad.salud.movil`) y recursos SMB `archivos` y `contenido` |
| `clinica01/publicacion/` | clinica01 → comunidad01 | Timer que copia el recurso `contenido` a comunidad01 con `rsync` por SSH, con un usuario de solo lectura y una llave que allá solo puede escribir en la carpeta de medios; se despliega con el rol `publicacion` de Ansible |
| `backups/` | kit01 → disco USB | Backup semanal con restic en modelo pull (configuraciones, recursos SMB, bases de PostgreSQL y dominio), con una llave que en las VMs solo ejecuta un comando forzado, el disco montado solo durante la copia, retención y restauración; se despliega con los roles `backups` y `backup_origen` de Ansible |
| `ansible/` | - | Inventarios del kit y del laboratorio virtual, plan de direcciones, secretos en `ansible-vault`, el rol `comun` (usuario compartido, sshd sin root, zona horaria, ufw en las VMs) el rol `kit01_base` (hostname, virtualización, red `default` de libvirt y NetBird retenido), el rol `kit01_vms` (VMs), el rol `bind9` (DNS), el rol `chrony` (NTP), el rol `samba_ad` (Samba AD DC y recursos SMB), el rol `ca_interna` (CA del kit), el rol `publicacion` (publicación de contenido) y los roles `backups` y `backup_origen` (backups) |

El diseño de referencia está en `docs/arquitectura/00-punto-de-partida.md` (secciones 7, 11 y 14).

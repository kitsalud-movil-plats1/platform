# platform

Servicios de plataforma del kit.

| Ruta | Host | Contenido |
|---|---|---|
| `kvm01/` | kvm01 | Netplan, bridges VLAN, definiciones libvirt, NUT (UPS simulada con `dummy-ups`) |
| `infra01/bind9/` | infra01 | Zona `salud.movil`, zonas inversas v4/v6 |
| `infra01/chrony/` | infra01 | Servidor NTP (`local stratum 10`) |
| `dc01/` | dc01 | Aprovisionamiento de Samba AD DC (`ad.salud.movil`) |
| `files01/` | files01 | Samba miembro (SMB) y exportaciones NFS |
| `backups/` | kvm01 | Scripts y timers de restic, política de retención |
| `ansible/` | - | Inventario y playbooks (secretos en `ansible-vault`) |

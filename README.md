# platform

Servicios de plataforma del kit.

| Ruta | Rol (VM) | Contenido |
|---|---|---|
| `nodos/` | kvm01, kvm02, kvm03 | Netplan, bridges VLAN, definiciones libvirt por perfil de despliegue, NUT (primario en kvm01 con `dummy-ups`, secundarios en los demás nodos) |
| `infra01/bind9/` | infra01 (VM infra01) | Zona `salud.movil`, zonas inversas v4/v6 |
| `infra01/chrony/` | infra01 (VM infra01) | Servidor NTP (`local stratum 10`) |
| `dc01/` | dc01 (VM infra01, IP `.11`) | Aprovisionamiento de Samba AD DC (`ad.salud.movil`) |
| `files01/` | files01 (VM ops01, IP `.12`) | Samba miembro (SMB) y exportaciones NFS |
| `backups/` | todas las VMs → files01 | Timers de restic en cada VM, rest-server en modo append-only (repositorio en el disco USB), política de retención |
| `ansible/` | - | Inventario y playbooks (secretos en `ansible-vault`) |

Qué VM corre en qué nodo depende del perfil de despliegue (sección 10.3 de `docs/arquitectura/00-punto-de-partida.md`).

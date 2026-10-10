# kit01, Beelink EQi12

Router/firewall e hipervisor del kit (D-02, D-04, sección 6 del documento). La ficha del equipo está en `workspace/contexto/equipos/kit01-beelink-eqi12.md`.

## Inventario (2026-10-09)

| Dato | Valor | Cómo se obtuvo |
|---|---|---|
| Fabricante / modelo (DMI) | AZW / EQ (Beelink EQi12) | `hostnamectl` |
| BIOS | `EQI12D405` | `dmidecode -s bios-version` |
| CPU | 12th Gen Intel Core i3-1220P, 12 hilos | `lscpu` |
| Virtualización | **VT-x activa** | `lscpu \| grep -i virt` |
| RAM | 15 GiB utilizables (16 GB) | `free -h` |
| Disco | NVMe de 476,9 GiB (500 GB), con `/boot/efi` de 1 GB, `/boot` de 2 GB y LVM `ubuntu-vg` de 473,9 GiB con `/` de 100 GiB (el resto del grupo queda libre para las VMs) | `lsblk` |
| NIC 1 | `enp170s0`, MAC `78:55:36:09:07:0b`, Realtek RTL8111 (`r8169`) → **WAN** (rol `wan0`) | `ip -br link`, `lspci -k` |
| NIC 2 | `enp171s0`, MAC `78:55:36:09:07:0a`, Realtek RTL8111 (`r8169`) → **trunk a sw01 ether1** (rol `lan0`) | `ip -br link`, `lspci -k` |
| "Restore on AC power loss" | Sin revisar; opcional, porque exige ir al laboratorio | - |
| Disco USB de backups | No conectado todavía | - |

En la misma sesión se verificaron los equipos de red, sw01 con RouterOS 7.13.5 (RouterBOOT `al64` 7.13.5); AP con firmware 3.16.9 Build 150723.

## Instalación

| Elemento | Estado |
|---|---|
| Sistema | Ubuntu Server 24.04.5 LTS, kernel 6.8.0-139, LVM |
| Hostname | `kitsalud-server` → pendiente cambiar a `kit01` |
| Usuario de administración | `kitsalud`, compartido por el grupo (D-18), con sudo |
| SSH | Con contraseña. `PermitRootLogin` en `without-password` (valor por defecto) → pendiente dejarlo en `no` |
| Red | Netplan provisional, en `network/kit01/netplan/` |
| NetBird | Instalado (0.80.0) y conectado, ver [`netbird/`](netbird/) |
| Virtualización | `qemu-kvm` y `libvirt` sin instalar → pendiente |

## Pendiente (`platform#2`)

- Hostname `kit01`.
- `PermitRootLogin no`.
- `apt full-upgrade`, `qemu-kvm`, `libvirt-daemon-system`, `virtinst` y `virt-host-validate`.

Todo se hace en remoto por NetBird. Las NIC no se renombran (D-14) y, si `apt full-upgrade` pide reiniciar, el reinicio se deja para una visita con alguien en el laboratorio (P12).

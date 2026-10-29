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
| Sistema | Ubuntu Server 24.04.5 LTS con LVM, actualizado el 2026-10-10. Corre el kernel 6.8.0-139 y el 6.8.0-146 queda instalado para el próximo arranque |
| Hostname | `kit01` (`kit01.salud.movil` en `/etc/hosts`). cloud-init está desactivado, así que no lo cambia al arrancar |
| Usuario de administración | `kitsalud`, compartido por el grupo (D-18), con sudo y en los grupos `libvirt` y `kvm` |
| SSH | Con contraseña y `PermitRootLogin no`, con el drop-in `10-comun.conf` del rol `comun` de Ansible ([`../ansible/`](../ansible/)). Escucha en IPv4 e IPv6 |
| Zona horaria | `America/Bogota`, del rol `comun` |
| Red | Netplan en `network/kit01/netplan/`, reenvío en `network/kit01/sysctl/` y firewall en `network/kit01/nftables/` |
| NetBird | 0.80.0, conectado y retenido con `apt-mark hold`, ver [`netbird/`](netbird/) |
| Virtualización | QEMU 8.2.2 (`qemu-system-x86`, que provee `qemu-kvm`), libvirt 10.0.0 y virt-install 4.1.0. La red `default` de libvirt (`virbr0`) está detenida y sin arranque automático, porque las VMs van a `br-srv` y `br-com` |
| VMs | `clinica01` y `comunidad01`, con sus discos en el LV `ubuntu-vg/vms` (320 GiB) montado en `/var/lib/libvirt/images`; ver [`libvirt/`](libvirt/) |

### Cómo se despliega

Todo se hace en remoto por NetBird (D-23), sin tocar `enp170s0`, netplan, nftables ni la configuración de NetBird. Desde `platform/ansible/`, en este orden:

```bash
ansible-playbook playbooks/comun.yml -l kit01      # usuario compartido (con los grupos libvirt y kvm), sshd sin root y zona horaria
ansible-playbook playbooks/kit01.yml --check --diff # qué cambiaría en la base del hipervisor
ansible-playbook playbooks/kit01.yml                # rol kit01_base
ansible-playbook playbooks/vms.yml                  # LV de las VMs y VMs (rol kit01_vms)
```

El rol `kit01_base` ([`../ansible/roles/kit01_base/`](../ansible/roles/kit01_base/)) deja así la base del hipervisor.

| Qué | Cómo |
|---|---|
| Hostname | `kit01` con `hostnamectl` (módulo `hostname`) y `127.0.1.1 kit01.salud.movil kit01` en `/etc/hosts`. Solo toca esa línea; las de `dc01.ad.salud.movil` las ponen los roles `grafana` y `samba_ad` |
| Virtualización | `qemu-kvm` (paquete virtual que provee `qemu-system-x86`), `libvirt-daemon-system` y `virtinst`, solo si faltan. Sin versión fija ni `hold`, y sin `apt update` ni actualización |
| Red `default` de libvirt | Se lee con `virsh net-info` y solo si está activa o con arranque automático se detiene (`net-destroy`) o se le quita (`net-autostart --disable`). Con `--check`, esas dos tareas informan el cambio sin ejecutar `virsh` |
| NetBird | Retenido (`dpkg_selections: hold`) para que no se actualice con el resto. Su configuración no se toca |

No reinicia ni actualiza paquetes, así que una segunda ejecución termina con `changed=0`.

**Actualizar paquetes.** Se hace a mano en la ventana de mantenimiento (R-05), con NetBird retenido y sin reiniciar. `systemd-run` evita que dpkg quede a medias si se corta la sesión.

```bash
sudo apt-get update
sudo systemd-run --unit=kit01-apt --setenv=DEBIAN_FRONTEND=noninteractive --setenv=NEEDRESTART_MODE=l \
  apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade
journalctl -u kit01-apt -f
```

`NEEDRESTART_MODE=l` hace que needrestart solo liste los servicios con bibliotecas viejas. Esos servicios y el kernel nuevo se activan con el reinicio de P12. `open-iscsi` y `libopeniscsiusr` pueden quedar sin actualizar, porque Ubuntu publica esas versiones de forma escalonada (`phased`) y apt las difiere solo. La copia de la configuración anterior a la instalación está en `/root/respaldo-platform2/`.

### Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `hostnamectl --static; hostname -f` | `kit01` y `kit01.salud.movil` |
| `sudo sshd -T \| grep -iE '^(permitrootlogin\|passwordauthentication) '` | `permitrootlogin no` y `passwordauthentication yes` |
| `ss -tln 'sport = :22'` | Escucha en `0.0.0.0:22` y `[::]:22` |
| `apt list --upgradable; sudo dpkg --audit` | Solo paquetes en publicación escalonada; `dpkg --audit` vacío |
| `apt-mark showhold` | `netbird` |
| `virsh -c qemu:///system version` | libvirt 10.0.0 y QEMU 8.2.2 |
| `virsh -c qemu:///system net-list --all` | `default` inactiva y con `Autostart no` |
| `sudo virt-host-validate qemu` | Todo en `PASS` salvo el `WARN` de "secure guest support" (SEV y TDX, que las VMs del kit no usan) |
| `ip -br addr` | `enp170s0` con `192.168.160.69/24`, `enp171s0` en `UP`, `lan0.10` y `wt0` con sus direcciones |
| `sudo netbird status` | `Management` y `Signal` en `Connected` |
| `ansible-playbook playbooks/kit01.yml --check --diff` (desde `platform/ansible/`) | `changed=0` |

### Diagnóstico

- **`sudo` avisa "unable to resolve host".** Falta la línea `127.0.1.1 kit01.salud.movil kit01` en `/etc/hosts`.
- **`sshd -T` no muestra `permitrootlogin no`.** Revisar que exista `/etc/ssh/sshd_config.d/10-comun.conf` (rol `comun`). sshd usa el primer valor que lee, así que el nombre del archivo debe ordenarse antes de `50-cloud-init.conf`.
- **Aparece `virbr0` o reglas dentro de las cadenas `LIBVIRT_*`.** La red `default` volvió a arrancar; se detiene con `ansible-playbook playbooks/kit01.yml` (o con `virsh net-destroy default` y `virsh net-autostart --disable default`). Las cadenas `LIBVIRT_*` vacías y sus saltos son normales, porque libvirt las crea al iniciar aunque no haya redes activas.
- **Una actualización quedó a medias.** `journalctl -u kit01-apt` muestra dónde se detuvo y `sudo dpkg --configure -a` la termina.

## Pendiente para el reinicio de P12

- Arrancar con el kernel 6.8.0-146 y comprobar con `uname -r`, `ip -br link` (las NIC conservan `enp170s0` y `enp171s0`, D-14), `hostnamectl` y `netbird status`.
- Quitar el kernel 6.8.0-139 con `apt autoremove` después de comprobar el arranque.
- Opcional, "Restore on AC power loss" en la BIOS.

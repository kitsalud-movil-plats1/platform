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

### Cómo se instaló

Todo se hizo en remoto por NetBird (D-23), sin tocar `enp170s0`, netplan, nftables ni NetBird. La copia de lo anterior quedó en `/root/respaldo-platform2/`. Lo que hoy maneja Ansible (SSH, zona horaria y usuario) está en el rol `comun`; lo demás se pasará a Ansible en su propia tarea.

```bash
# Hostname, en un solo comando para que sudo siga resolviendo el nombre
sudo hostnamectl set-hostname kit01 && \
  sudo sed -i 's/^127\.0\.1\.1.*/127.0.1.1 kit01.salud.movil kit01/' /etc/hosts

# SSH sin root, zona horaria y usuario compartido: rol comun de Ansible (platform/ansible)
#   ansible-playbook playbooks/comun.yml

# Actualización sin reiniciar. systemd-run evita que dpkg quede a medias si se corta la sesión
sudo apt-mark hold netbird
sudo apt-get update
sudo systemd-run --unit=kit01-apt --setenv=DEBIAN_FRONTEND=noninteractive --setenv=NEEDRESTART_MODE=l \
  apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade
journalctl -u kit01-apt -f

# Virtualización, de la misma forma
sudo systemd-run --unit=kit01-virt --setenv=DEBIAN_FRONTEND=noninteractive --setenv=NEEDRESTART_MODE=l \
  apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install qemu-kvm libvirt-daemon-system virtinst
sudo virsh -c qemu:///system net-destroy default
sudo virsh -c qemu:///system net-autostart --disable default
sudo usermod -aG libvirt,kvm kitsalud
```

`NEEDRESTART_MODE=l` hace que needrestart solo liste los servicios con bibliotecas viejas. Esos servicios y el kernel nuevo se activan con el reinicio de P12. `open-iscsi` y `libopeniscsiusr` pueden quedar sin actualizar, porque Ubuntu publica esas versiones de forma escalonada (`phased`) y apt las difiere solo.

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

### Diagnóstico

- **`sudo` avisa "unable to resolve host".** Falta la línea `127.0.1.1 kit01.salud.movil kit01` en `/etc/hosts`.
- **`sshd -T` no muestra `permitrootlogin no`.** Revisar que exista `/etc/ssh/sshd_config.d/10-comun.conf` (rol `comun`). sshd usa el primer valor que lee, así que el nombre del archivo debe ordenarse antes de `50-cloud-init.conf`.
- **Aparece `virbr0` o reglas dentro de las cadenas `LIBVIRT_*`.** La red `default` volvió a arrancar; se detiene con `virsh net-destroy default` y `virsh net-autostart --disable default`. Las cadenas `LIBVIRT_*` vacías y sus saltos son normales, porque libvirt las crea al iniciar aunque no haya redes activas.
- **Una actualización quedó a medias.** `journalctl -u kit01-apt` muestra dónde se detuvo y `sudo dpkg --configure -a` la termina.

## Pendiente para el reinicio de P12

- Arrancar con el kernel 6.8.0-146 y comprobar con `uname -r`, `ip -br link` (las NIC conservan `enp170s0` y `enp171s0`, D-14), `hostnamectl` y `netbird status`.
- Quitar el kernel 6.8.0-139 con `apt autoremove` después de comprobar el arranque.
- Opcional, "Restore on AC power loss" en la BIOS.

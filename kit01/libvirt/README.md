# VMs de kit01 (libvirt)

kit01 es el hipervisor de `clinica01` y `comunidad01` (D-04, D-19, sección 10.1 del documento). Las VMs se crean y se configuran con Ansible, con el rol `kit01_vms` y el playbook `playbooks/vms.yml` de [`../../ansible/`](../../ansible/). Este directorio documenta cómo quedan.

| VM | vCPU | RAM | Discos | MAC | Direcciones |
|---|---|---|---|---|---|
| `clinica01` | 4 | 7 GB | 40 GB sistema + 120 GB datos (`/srv`) | `52:54:00:20:00:11` | `10.20.20.11/24`, `fd5a:fc7e:d716:20::11/64` |
| `comunidad01` | 2 | 2,5 GB | 20 GB sistema + 120 GB datos (`/srv`) | `52:54:00:20:00:12` | `10.20.20.12/24`, `fd5a:fc7e:d716:20::12/64` |

Las definiciones están en `ansible/inventarios/kit/group_vars/all/maquinas.yml`.

## Cómo son

- **Red.** Una interfaz virtio en `br-srv` con MAC fija. IP estática v4 y v6, ruta por defecto IPv4 `via 10.20.20.1` e IPv6 `via fe80::1` (on-link), DNS `10.20.20.10` y `fd5a:fc7e:d716:20::10`, sin RA ni DHCP.
- **Discos.** qcow2 con aprovisionamiento delgado e independientes, sin archivo base compartido, así que se pueden copiar tal cual a otro equipo (10.4). Viven en el LV `ubuntu-vg/vms` (320 GiB, ext4), montado en `/var/lib/libvirt/images` con `nofail`. Si el montaje fallara al arrancar, kit01 arranca igual y solo las VMs no encuentran sus discos.
- **Imagen base.** Ubuntu 24.04 cloud `release-20260926`, verificada con `SHA256SUMS`, en `/var/lib/libvirt/images/base/`.
- **Primer arranque.** cloud-init pone el hostname, la zona horaria, el usuario compartido con el hash del vault (SSH con contraseña, sin root), formatea el disco de datos (`LABEL=datos`) y lo monta en `/srv`. Al terminar deja `/etc/cloud/cloud-init.disabled`; desde ahí la configuración la maneja Ansible. El ISO de cloud-init lo crea `virt-install`, que lo borra y lo deja fuera de la definición persistente.
- **Base común.** El rol `comun` deja `PermitRootLogin no`, `America/Bogota` y `ufw` con entrada denegada y SSH solo desde las direcciones de kit01 en `br-srv` (`10.20.20.1`, `.10`, `fd5a:fc7e:d716:20::1`, `::10` y `fe80::1`).
- **Arranque.** Las dos tienen `autostart` de libvirt. No hay un retardo entre ellas; el orden entre servicios lo resuelven las aplicaciones con reintentos y healthchecks (sección 6.5). Cambiar de perfil (10.3) es `virsh autostart <vm>` o `virsh autostart --disable <vm>`.
- **Sin Internet todavía.** El firewall de kit01 no deja salir a las VMs hasta que se abra F-17.

## Cómo se crean y se recrean

Desde `platform/ansible/`, una vez por máquina de control:

```bash
ansible-playbook playbooks/preparar-control.yml   # crea ~/.config/kitsalud/ssh-pass desde el vault
```

Después:

```bash
ansible-playbook playbooks/vms.yml
```

El playbook crea el LV, descarga la imagen y crea las VMs que falten. Una VM que ya existe no se toca. Para recrear una desde cero:

```bash
ansible kit01 -b -m shell -a 'virsh destroy comunidad01; virsh undefine comunidad01 --remove-all-storage'
ansible-playbook playbooks/vms.yml
```

El rol borra de `known_hosts` local la clave SSH de la VM anterior con la misma IP, espera el SSH de la VM nueva y que cloud-init termine, y aplica el rol `comun`.

## Acceso

A las VMs solo se llega a través de kit01 (D-18). Desde la Interna, el firewall de kit01 lo bloquea y lo registra, y dentro de la VM `ufw` también lo bloquea.

```bash
ssh -J kitsalud@100.90.225.113 kitsalud@10.20.20.11   # pide la contraseña dos veces
```

Ansible usa el mismo salto, con `sshpass -f ~/.config/kitsalud/ssh-pass` para kit01 (ver `ansible/inventarios/kit/group_vars/vms.yml`).

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `virsh list --all` y `virsh dominfo <vm> \| grep Autostart` | Las dos `running`, con `Autostart: enable` |
| `virsh domiflist <vm>` | Interfaz en `br-srv` con su MAC |
| Desde kit01, `ping` a `10.20.20.11`, `.12`, `fd5a:fc7e:d716:20::11` y `::12` | Responden |
| `ansible vms -m ping` | `pong` de las dos |
| En cada VM, `ping -6 fd5a:fc7e:d716:20::1` y `ping 10.20.20.1` | Responden |
| Desde un equipo de la Interna, SSH a `10.20.20.11` | Sin respuesta; en kit01, `journalctl -k \| grep fw-drop` muestra `IN=lan0.10 OUT=br-srv ... DPT=22` |
| `ansible-playbook playbooks/vms.yml` dos veces | La segunda termina con `changed=0` |

## Diagnóstico

- **Una VM no arranca después de reiniciar kit01.** `findmnt /var/lib/libvirt/images`; si el LV no se montó, `sudo mount /var/lib/libvirt/images` y `virsh start <vm>`.
- **Ansible no llega a una VM.** Comprobar que exista `~/.config/kitsalud/ssh-pass` y que la VM responda desde kit01 (`ping 10.20.20.11`). Si la VM se recreó a mano, borrar su clave vieja con `ssh-keygen -R 10.20.20.11`.
- **La VM no tiene red.** `virsh console <vm>` y revisar `/etc/netplan/50-cloud-init.yaml`; la MAC de la definición tiene que coincidir con la del network-config.
- **La VM no responde al eco hacia otra red.** Es lo esperado; desde `br-srv` el eco solo se permite hacia su gateway (F-23).

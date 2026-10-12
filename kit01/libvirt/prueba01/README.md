# prueba01

VM de prueba conectada a `br-com`, que hace de celular de la Comunidad (VLAN 40) para validar en remoto DHCPv4, IPv6, DNS, portal y firewall (D-24). Las pruebas con Wi-Fi y celulares se confirman en la visita final.

| Dato | Valor |
|---|---|
| Recursos | 1 vCPU, 512 MB, disco de 10 GB, sin disco de datos |
| Red | `br-com`, MAC fija `52:54:00:40:00:50`, link-local `fe80::5054:ff:fe40:50` |
| Direcciones | DHCPv4 y SLAAC/DHCPv6 sin estado, como un cliente de la red. Por DHCPv4 recibe una dirección de `10.20.40.100-250`; hasta radvd (network#6) su IPv6 es solo la link-local |
| Arranque | Sin `autostart`. Se enciende solo para las pruebas y no cuenta en los totales ni en los perfiles por misión |
| Configuración | Solo cloud-init (usuario compartido con el hash del vault, SSH sin root, zona horaria); sin el rol `comun` ni `ufw` |
| Herramientas | `dig`, `curl`, `ping` (vienen en la imagen cloud) |

La definición está en `ansible/inventarios/kit/group_vars/all/maquinas.yml` y se crea con el rol `kit01_vms` (`playbooks/vms.yml`), igual que las demás VMs.

## Cómo se usa

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/prueba01.yml                           # encender y esperar el SSH
ansible prueba01 -m shell -a 'ip -br addr; dig pacientes.salud.movil'
ansible-playbook playbooks/prueba01.yml -e prueba01_estado=apagada
```

El SSH nace en kit01 hacia la link-local de la VM, porque el firewall no permite gestión desde la Comunidad hacia kit01. A mano:

```bash
ssh kitsalud@100.90.225.113
ssh kitsalud@fe80::5054:ff:fe40:50%br-com      # o, como respaldo, sudo virsh console prueba01
```

Para recrearla desde cero:

```bash
ansible kit01 -b -m shell -a 'virsh destroy prueba01; virsh undefine prueba01 --remove-all-storage'
ansible-playbook playbooks/vms.yml
ansible-playbook playbooks/prueba01.yml -e prueba01_estado=apagada
```

## Pruebas habituales (desde prueba01)

| Prueba | Comando | Resultado esperado | Desde |
|---|---|---|---|
| Dirección IPv4 | `ip -4 -br addr show eth0` | `10.20.40.100-250/24` | network#5 |
| Dirección IPv6 y ruta | `ip -6 -br addr show eth0; ip -6 route show default` | `fd5a:fc7e:d716:40::/64` por SLAAC y `default via fe80::1` | network#6 |
| DNS | `dig pacientes.salud.movil A` y `AAAA` | `10.20.20.11` y `fd5a:fc7e:d716:20::11` | network#5 |
| Eco al gateway (F-23) | `ping -c2 10.20.40.1; ping -6 -c2 fe80::1%eth0` | Responden | network#5 |
| Aislamiento (F-20, P3) | `curl -m5 https://pacientes.salud.movil; ping -c2 10.20.10.1` | Sin respuesta; en kit01, `journalctl -k \| grep fw-drop` con `IN=br-com` | network#5 |
| Portal (F-08) | `curl -sI http://neverssl.com` | Redirección a `portal.salud.movil` | network#8 |

## Cómo se verifica

| Comando (en kit01) | Resultado esperado |
|---|---|
| `virsh list --all` | `prueba01` en `shut off` cuando no se usa |
| `virsh dominfo prueba01 \| grep Autostart` | `disable` |
| Encendida, `bridge link \| grep br-com` | `vnet*` y `lan0.40` en `br-com` |
| Encendida, `ping -6 -c2 fe80::5054:ff:fe40:50%br-com` | Responde |

## Diagnóstico

- **Tarda unos 2 minutos en arrancar.** Pasa si Kea no responde: sin DHCP, el arranque espera la red antes de levantar SSH. Con Kea arranca en unos 30 s.
- **Ansible no llega.** Revisar que esté encendida (`virsh domstate prueba01`) y que exista `~/.config/kitsalud/ssh-pass`.

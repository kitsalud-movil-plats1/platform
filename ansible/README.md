# Ansible del kit

Base de Ansible del kit (D-17, E2, E7). Desde aquí se configuran kit01 y las VMs con los roles de todos los repositorios.

## Estructura

| Ruta | Contenido |
|---|---|
| `ansible.cfg` | Inventario por defecto (`inventarios/kit`), `roles_path` hacia `roles/` y hacia `../../{network,apps,observability}/ansible/roles`, y la contraseña del vault en `~/.config/kitsalud/vault-pass` |
| `inventarios/kit/` | kit01 por NetBird, y clinica01 y comunidad01 a través de kit01 |
| `inventarios/lab/` | El laboratorio virtual (`workspace/lab-virtual`), con `kitlab-kit01` como `kit01` y `kitlab-cliente` como VM de prueba |
| `inventarios/kit/group_vars/all/red.yml` | Plan de direcciones (secciones 7 y 8). Se define solo aquí; el inventario del laboratorio lo enlaza |
| `inventarios/kit/group_vars/all/maquinas.yml` | Definición de las VMs (vCPU, RAM, discos, MAC, IP, autostart) |
| `inventarios/kit/group_vars/all/vault.yml` | Secretos cifrados con `ansible-vault`. Sus claves están en [`vault.example.yml`](vault.example.yml) |
| `inventarios/*/host_vars/kit01.yml` | Nombres de interfaz de cada rol (`iface_wan`, `iface_lan`, D-14, R-08) y ajustes propios de kit01 |
| `playbooks/comun.yml` | Aplica el rol `comun` a todos los hosts |
| `playbooks/vms.yml` | Crea las VMs que falten en kit01 (rol `kit01_vms`) y les aplica el rol `comun` |
| `playbooks/clinica01.yml` | Aplicaciones de clinica01 con los roles `docker` y `dhis2` del repositorio `apps` (`-e dhis2_estado=stopped` para detener DHIS2) |
| `playbooks/preparar-control.yml` | Crea `~/.config/kitsalud/ssh-pass` desde el vault, para el salto por kit01 |
| `roles/comun/` | Base común de kit01 y las VMs |
| `roles/kit01_vms/` | LV `vms`, imagen base y VMs con cloud-init (ver `kit01/libvirt/README.md`) |

Los roles de cada componente viven en su repositorio (`<repo>/ansible/roles/`) y se encuentran por `roles_path`, así que los repositorios tienen que estar clonados uno al lado del otro, como en el espacio de trabajo.

## Rol `comun`

| Qué | Dónde aplica | Detalle |
|---|---|---|
| Usuario de administración compartido (D-18) | Todos | `kitsalud` con sudo. Se crea con el hash del vault y nunca cambia una contraseña existente (`update_password: on_create`). Los grupos extra van por host (`comun_admin_grupos_extra`; en kit01, `libvirt` y `kvm`) |
| sshd sin root | Todos | `/etc/ssh/sshd_config.d/10-comun.conf` con `PermitRootLogin no`. Borra el `10-kit01.conf` de platform#2. Antes de recargar valida con `sshd -t` |
| Zona horaria | Todos | `America/Bogota` (`comun_zona_horaria`) |
| ufw | Solo el grupo `vms` (`comun_ufw`) | Entrada denegada y SSH solo desde kit01 (`comun_ufw_ssh_origenes`). En kit01 filtra nftables y ufw no se toca |
| Cliente Chrony | Apagado (`comun_chrony_cliente`) | Fuente `ntp.salud.movil`; se enciende en platform#6 |
| Reenvío de rsyslog | Apagado (`comun_rsyslog_reenvio`) | TCP 514 hacia `10.20.20.10` con cola; se enciende en observability#3 |
| DNS temporal | Grupo `vms` (`comun_dns_temporal`) | Drop-in de `systemd-resolved` con los DNS del sitio mientras no exista BIND9. Con la lista vacía (platform#5) se borra |

## Secretos

`vault.yml` está cifrado y se versiona. La contraseña del vault no se versiona. Cada integrante la guarda en `~/.config/kitsalud/vault-pass` (permisos `600`) y se comparte por un canal privado del grupo. Para ver o editar los secretos se usan `ansible-vault view` y `ansible-vault edit` sobre `inventarios/kit/group_vars/all/vault.yml`.

Para crear el vault desde cero:

```bash
install -d -m 700 ~/.config/kitsalud
(umask 077; openssl rand -base64 32 > ~/.config/kitsalud/vault-pass)
openssl passwd -6                     # pide la contraseña del usuario compartido y muestra su hash
ansible-vault create inventarios/kit/group_vars/all/vault.yml   # mismas claves que vault.example.yml
```

## Acceso a las VMs

Las VMs solo aceptan SSH desde kit01 (D-18), así que Ansible salta por kit01. Los dos saltos usan la contraseña del usuario compartido y `sshpass` solo contesta un aviso, así que el salto por kit01 lee la contraseña de `~/.config/kitsalud/ssh-pass` (`600`, fuera del repositorio). Ese archivo lo crea `playbooks/preparar-control.yml` desde el vault, una vez por máquina de control. Expone lo mismo que `vault-pass`, que ya está en esa carpeta.

## Uso

Siempre desde `platform/ansible/`, para que se lea `ansible.cfg`.

```bash
ansible-playbook playbooks/preparar-control.yml          # una vez por máquina de control
ansible all -m ping                                        # kit real
ansible-playbook playbooks/comun.yml --check --diff        # qué cambiaría
ansible-playbook playbooks/comun.yml                       # aplicar
ansible-playbook playbooks/vms.yml                         # VMs
ansible-playbook -i inventarios/lab playbooks/comun.yml    # laboratorio virtual
```

En el laboratorio virtual se entra con la llave de cada integrante (`LAB_USUARIO`, por defecto el usuario local) y sudo no pide contraseña. El rol crea ahí el usuario compartido igual que en el kit.

Antes de un cambio en kit01 que pueda cortar el acceso, se programa la restauración como en `AGENTS.md`, sección 6. Por ejemplo, para sshd:

```bash
sudo systemd-run --on-active=120 --unit=ssh-rollback sh -c 'rm -f /etc/ssh/sshd_config.d/10-comun.conf && systemctl reload ssh'
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `ansible all -m ping` | `pong` de kit01, clinica01 y comunidad01 |
| `ansible-playbook playbooks/comun.yml` dos veces | La segunda termina con `changed=0` en todos los hosts |
| `git grep -i -E 'password\|secret'` | Solo nombres de variables y textos, ningún valor |
| `ansible all -b -m command -a 'sshd -T' \| grep -i permitrootlogin` | `permitrootlogin no` |
| `ansible kit01 -b -m command -a 'ufw status'` | `Status: inactive` |

## Diagnóstico

- **`The vault password file ... was not found`.** Falta `~/.config/kitsalud/vault-pass`.
- **`Decryption failed`.** La contraseña del vault no es la del grupo.
- **No conecta a kit01.** Comprobar NetBird (`netbird status` en la máquina propia) y que el host de `inventarios/kit/hosts.yml` sea la IP de NetBird de kit01. Las conexiones por contraseña necesitan `sshpass` en la máquina que ejecuta Ansible.
- **El handler de sshd falla con `sshd -t`.** El drop-in ya quedó escrito, pero sshd no se recargó y sigue con la configuración anterior. Corregir el archivo y volver a ejecutar.

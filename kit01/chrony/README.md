# Chrony en kit01

Servidor de hora del kit (R3, P8), en la IP de servicios (`ntp.salud.movil`). Lo instala y configura el rol `chrony` de [`../../ansible/`](../../ansible/) con `playbooks/ntp.yml`. Los clientes de las VMs los configura el rol `comun`.

| Elemento | Valor |
|---|---|
| Paquete | `chrony` 4.5-1ubuntu4.2, retenido con `hold` (la versión está en `inventarios/kit/group_vars/all/paquetes.yml`). Reemplaza a `systemd-timesyncd` |
| Fuentes | `pool pool.ntp.org iburst maxsources 4` |
| Sin Internet | `local stratum 10 orphan`. kit01 conserva la última referencia y, si el corte se alarga, sigue sirviendo hora como stratum 10 |
| Escucha | Solo `10.20.20.10:123` y `[fd5a:fc7e:d716:20::10]:123` (`bindaddress`) |
| Acceso | `allow` para `10.20.0.0/16` y `fd5a:fc7e:d716::/48`; el firewall de kit01 deja el 123 hacia `.10` desde la Interna, la Comunidad y `br-srv` (F-03) |

## Clientes

| Cliente | Cómo | Estado esperado |
|---|---|---|
| clinica01, comunidad01 | Rol `comun` con `comun_chrony_cliente: true` (grupo `vms`). Su `chrony.conf` solo tiene `server ntp.salud.movil iburst`, sin los pools de Ubuntu, porque el firewall no deja salir a las VMs por el 123 | `^*` en `ntp.salud.movil`, stratum 4 |
| sw01 | `/system ntp client set enabled=yes` y servidor `10.20.20.10` (`network/switch/sw01.rsc`) | `status: synchronized` |
| ap01 | No aplica. El TL-WA801ND v3 (firmware 3.16.9) no tiene ajustes de hora y tampoco envía syslog | - |
| Estaciones de la Interna y la Comunidad | NTP por DHCPv4 y DHCPv6 (network#5, network#6) | - |

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/ntp.yml                 # servidor en kit01
ansible-playbook playbooks/comun.yml --limit vms   # clientes en las VMs
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `chronyc tracking` en kit01 | `Stratum` 2 o 3 con Internet, `Leap status: Normal` |
| `chronyc sources` en kit01 | Una fuente del pool con `^*` |
| `ss -lnup 'sport = :123'` en kit01 | Solo `10.20.20.10` y `[fd5a:fc7e:d716:20::10]` |
| `chronyc -N sources` en una VM | `^* ntp.salud.movil` (`chronyc sources` sin `-N` muestra `ns1.salud.movil`, que es el PTR de `10.20.20.10`) |
| `/system ntp client print` en sw01 | `status: synchronized`, `synced-server: 10.20.20.10` |

**Sin WAN.** Para probarlo sin desconectar el cable, una tabla temporal descarta el NTP que sale por la WAN y se borra sola:

```bash
sudo nft -f - <<'EOF'
table inet prueba_sin_wan_ntp {
  chain output { type filter hook output priority filter; policy accept;
    oifname "enp170s0" udp dport 123 counter drop; }
}
EOF
sudo systemd-run --on-active=600 --unit=prueba-sin-wan-ntp nft delete table inet prueba_sin_wan_ntp
```

A los 9 minutos, kit01 seguía en stratum 3 con `Leap status: Normal` y las VMs y sw01 seguían sincronizadas con él.

## Diagnóstico

- **Una VM no sincroniza.** `chronyc -N sources` en la VM y `dig @10.20.20.10 ntp.salud.movil` (resuelve con BIND9). Desde kit01, `chronyc clients` muestra quién consulta.
- **kit01 en stratum 10 con Internet.** No llega al pool: `chronyc sources` y la salida por el 123 hacia la WAN.
- **Un cliente queda en `^?`.** El firewall o `allow` lo bloquean; revisar `journalctl -k | grep fw-drop` y que la IP esté en `10.20.0.0/16` o en la ULA.

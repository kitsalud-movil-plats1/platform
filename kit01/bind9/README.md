# BIND9 en kit01

DNS autoritativo y recursivo del kit (R2, sección 9 del documento). Lo instala y configura el rol `bind9` de [`../../ansible/`](../../ansible/) con `playbooks/dns.yml`. Los nombres están en `ansible/inventarios/kit/group_vars/all/dns.yml` y las direcciones salen de `red.yml`, así que cada IP se define una sola vez.

| Elemento | Valor |
|---|---|
| Paquete | `bind9` 1:9.18.39-0ubuntu0.24.04.7, retenido con `hold` |
| Escucha | Solo `10.20.20.10` y `fd5a:fc7e:d716:20::10`, puerto 53. El 53 de NetBird (`100.90.225.113`) y el de systemd-resolved (`127.0.0.53` y `127.0.0.54`) no se tocan |
| Zonas | `salud.movil`, `20.10.in-addr.arpa` (la de `10.20.0.0/16`) y `6.1.7.d.e.7.c.f.a.5.d.f.ip6.arpa` (la de `fd5a:fc7e:d716::/48`), en `/etc/bind/zonas/` |
| Consultas y recursión | Solo desde `10.20.0.0/16`, `fd5a:fc7e:d716::/48` y localhost. Sin transferencias de zona |
| Reenviadores | `1.1.1.1` y `9.9.9.9` con `forward first`; si no responden, resuelve desde la raíz. `dnssec-validation auto` |
| Sin Internet | Las tres zonas son autoritativas y responden igual; lo externo devuelve `SERVFAIL` |
| Logs | Consultas en `/var/log/named/consultas.log` y el resto en `/var/log/named/named.log`, con rotación por tamaño |

## Nombres

| Nombre (`.salud.movil`) | A | AAAA |
|---|---|---|
| `pacientes`, `archivos`, `consultas`, `clinica01` | `10.20.20.11` | `fd5a:fc7e:d716:20::11` |
| `dc01.ad` | `10.20.20.11` | `fd5a:fc7e:d716:20::11` |
| `biblioteca`, `videos`, `registro`, `comunidad01` | `10.20.20.12` | `fd5a:fc7e:d716:20::12` |
| `ns1`, `ntp`, `monitoreo` | `10.20.20.10` | `fd5a:fc7e:d716:20::10` |
| `portal` | `10.20.40.1` | `fd5a:fc7e:d716:40::1` |
| `kit01`, `sw01` | `10.20.10.1`, `10.20.10.2` | `fd5a:fc7e:d716:10::1`, `::2` |
| `ap01` | `10.20.10.3` | - (el AP solo se gestiona por IPv4) |

`dc01.ad` es por ahora un registro normal de la zona. Cuando exista Samba AD (platform#8), `ad.salud.movil` se delega a clinica01 y ese registro pasa a ser el glue de la delegación.

Las inversas tienen un PTR por dirección: `kit01` (`10.20.10.1`, `10.20.20.1` y sus IPv6), `ns1` (`.10`), `portal`, `sw01`, `ap01`, `clinica01` y `comunidad01`.

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/dns.yml --check --diff
ansible-playbook playbooks/dns.yml
```

- **Arranque restringido.** El paquete se instala con un `policy-rc.d` temporal que impide arrancar `named`. Así nunca corre con la configuración de fábrica, que escucharía en todas las direcciones. Después el rol escribe la configuración y lo arranca.
- **Validación.** Cada zona se valida con `named-checkzone` antes de escribirse. Antes de recargar, el handler corre `named-checkconf -z` y, si falla, `named` sigue con la configuración anterior.
- **Serial.** El serial de cada zona sale del contenido (un hash), así que solo cambia cuando cambian los registros y Ansible sigue siendo idempotente. No hay servidores secundarios.
- **Nombres de las inversas.** Los calcula el filtro `nombre_ptr` del rol (`filter_plugins/dns.py`), con la biblioteca `ipaddress` de Python, sin dependencias.

Para agregar un nombre se edita `dns.yml` y se vuelve a ejecutar el playbook.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `sudo named-checkconf -z` | Carga las tres zonas sin errores |
| `ss -lnup 'sport = :53'` | `named` solo en `10.20.20.10` y `[fd5a:fc7e:d716:20::10]` |
| `dig @10.20.20.10 pacientes.salud.movil A` y `AAAA` | `10.20.20.11` y `fd5a:fc7e:d716:20::11`, con el flag `aa` |
| `dig @fd5a:fc7e:d716:20::10 -x 10.20.20.11` y `-x fd5a:fc7e:d716:20::11` | `clinica01.salud.movil.` |
| `dig @10.20.20.10 isc.org A +dnssec` | Respuesta con el flag `ad` (DNSSEC validado) |
| En sw01, `:put [:resolve domain-name=pacientes.salud.movil server=10.20.20.10]` | `10.20.20.11` |
| `sudo tail /var/log/named/consultas.log` | Las consultas con el cliente y la dirección por la que llegaron |

**Sin WAN.** Para probarlo sin desconectar el cable, una tabla temporal descarta solo el DNS que sale por la WAN, y se borra sola:

```bash
sudo nft -f - <<'EOF'
table inet prueba_sin_wan {
  chain output { type filter hook output priority filter; policy accept;
    oifname "enp170s0" meta l4proto { tcp, udp } th dport { 53, 853 } counter drop; }
}
EOF
sudo systemd-run --on-active=90 --unit=prueba-sin-wan nft delete table inet prueba_sin_wan
sudo rndc flush
dig @10.20.20.10 pacientes.salud.movil A    # responde
dig @10.20.20.10 wikipedia.org A            # SERVFAIL
```

## Diagnóstico

- **No responde.** `systemctl status named` y `sudo tail /var/log/named/named.log`. Si cambió la configuración, `sudo named-checkconf -z`.
- **Responde `REFUSED`.** El cliente no está en `10.20.0.0/16` ni en la ULA.
- **Lo externo da `SERVFAIL` con Internet.** `dig @1.1.1.1 ubuntu.com` desde kit01; si tampoco responde, el sitio bloquea el DNS hacia afuera y hay que revisar el reenvío o usar los DNS del sitio como reenviadores.
- **`named` no arranca después de un cambio de nombres.** Una zona inválida no se escribe, porque la valida `named-checkzone`. Revisar la salida del playbook.

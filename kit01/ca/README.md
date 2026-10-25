# CA interna del kit

Una sola raíz para todo el HTTPS del kit (D-16). La llave de la raíz vive solo en kit01. Cada VM tiene un intermedio que solo puede firmar sus propios nombres, y Caddy lo usa con `tls internal` para emitir y renovar solo sus certificados. Si alguien compromete comunidad01, la VM a la que llega la comunidad, su intermedio no sirve para falsificar `pacientes.salud.movil`.

| Pieza | Dónde | Vigencia | Qué firma |
|---|---|---|---|
| Raíz "Kit de salud movil - Raiz" (EC P-256) | kit01, `/etc/kitsalud/ca/raiz.crt` y `raiz.key` (`600`, carpeta `700`) | 10 años | Los intermedios y los certificados de kit01 |
| Intermedio "Kit de salud movil - clinica01" | clinica01, `/srv/caddy/pki/` | 2 años | Solo `pacientes`, `consultas` y `archivos` `.salud.movil` |
| Intermedio "Kit de salud movil - comunidad01" | comunidad01, `/srv/caddy/pki/` | 2 años | Solo `registro.salud.movil` |
| `monitoreo.salud.movil` | kit01, `/etc/kitsalud/tls/monitoreo.crt` y `.key` (`640`) | 397 días | Lo usa Grafana (observability#2) |
| Hojas de Caddy | Almacén de Caddy en cada VM | 12 horas | Caddy las renueva solo |

Los nombres de cada intermedio están en `ca_nombres` (`ansible/inventarios/kit/host_vars/<vm>.yml`) y van como *name constraints* críticas, así que un cliente rechaza cualquier certificado de otro nombre (`permitted subtree violation`). Los intermedios tienen `pathlen:0`: no pueden crear otras CA.

La llave de la raíz no está en ningún repositorio, ni siquiera en el vault. Se respalda con los backups de kit01 (platform#11). Si se pierde, se genera otra raíz y hay que volver a instalarla en los equipos.

## Cómo se despliega

Desde `platform/ansible/`, con el rol `ca_interna`.

```bash
ansible-playbook playbooks/ca.yml          # raíz y certificado de monitoreo en kit01
ansible-playbook playbooks/clinica01.yml   # intermedio de clinica01 y su Caddy
ansible-playbook playbooks/comunidad01.yml # intermedio de comunidad01, su Caddy y ca.salud.movil
```

- **Intermedios.** La llave y el CSR se generan en la VM. kit01 firma el CSR con la raíz (`community.crypto.x509_certificate`, `ownca`) y la VM recibe el certificado y la raíz. La llave del intermedio nunca sale de la VM y la de la raíz nunca sale de kit01.
- **Renovación.** El rol vuelve a firmar un intermedio si le quedan menos de 90 días o si cambian su llave o sus nombres, y el certificado de `monitoreo` si le quedan menos de 30. Cuando cambia la CA de una VM, borra los certificados que Caddy guardó y lo reinicia, para que emita los nuevos.
- **Publicación.** comunidad01 sirve la raíz y una página con instrucciones en `http://ca.salud.movil` (`ca_publicar` en su `host_vars`). La Interna llega ya; la Comunidad llegará con el portal (network#8).

## Cómo se instala en un equipo

Desde un equipo de la Interna se abre `http://ca.salud.movil` y se siguen las instrucciones para Android, iPhone, Windows o Linux. Antes de confiar en el archivo, su huella SHA-256 se compara con la de kit01.

```bash
openssl x509 -in raiz.crt -noout -fingerprint -sha256                         # en el equipo
sudo openssl x509 -in /etc/kitsalud/ca/raiz.crt -noout -fingerprint -sha256   # en kit01
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En kit01, `sudo stat -c '%a %U' /etc/kitsalud/ca/raiz.key` | `600 root` |
| En cada VM, `openssl x509 -in /srv/caddy/pki/intermedio.crt -noout -ext basicConstraints,nameConstraints` | `CA:TRUE, pathlen:0` y los nombres de la VM |
| `openssl verify -CAfile /srv/caddy/pki/raiz.crt /srv/caddy/pki/intermedio.crt` | `OK` |
| Desde la Interna, `curl --cacert raiz.crt https://pacientes.salud.movil/` por IPv4 e IPv6 | `302` sin error de certificado |
| `echo \| openssl s_client -connect 10.20.20.11:443 -servername pacientes.salud.movil -CAfile raiz.crt` | Cadena hoja → clinica01 → raíz y `Verify return code: 0 (ok)` |
| Una hoja de prueba para `pacientes` firmada con el intermedio de comunidad01 y `openssl verify -CAfile raiz.crt -untrusted intermedio.crt` | `permitted subtree violation` |
| `curl -I http://ca.salud.movil/raiz.crt` | `200` y `Content-Type: application/x-x509-ca-cert` |
| `git grep -l "PRIVATE KEY"` en los repositorios | Nada |

## Diagnóstico

- **El navegador sigue mostrando la advertencia.** La raíz no está instalada en ese equipo, o el navegador usa su propio almacén (Firefox).
- **`permitted subtree violation` con un nombre nuevo.** El nombre no está en `ca_nombres` de esa VM. Se agrega, se vuelve a ejecutar el playbook de la VM y el rol firma un intermedio nuevo.
- **Caddy entrega un certificado de la CA anterior.** El rol borra `/srv/caddy/data/caddy/certificates/local` al cambiar la CA; si se cambió a mano, borrarlo y `docker compose restart caddy`.
- **El playbook de una VM falla con "Primero ansible-playbook playbooks/ca.yml".** La raíz todavía no existe en kit01.

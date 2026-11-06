# NUT y apagado ordenado en kit01

El kit no tiene UPS física, así que la alimentación segura es lógica. NUT usa el driver `dummy-ups` con un archivo de estado que se cambia a mano para simular el corte. Con la UPS en batería y la batería baja, `upsmon` ejecuta `kit-apagado`, que apaga comunidad01, después clinica01 y al final kit01. Lo instala el rol `nut` de [`../../ansible/`](../../ansible/) con `playbooks/nut.yml`.

| Elemento | Valor |
|---|---|
| Paquetes | `nut-server` y `nut-client` 2.8.1-3.1ubuntu2, retenidos con `hold` (`version_nut` en `inventarios/kit/group_vars/all/paquetes.yml`) |
| UPS | `kit`, driver `dummy-ups` en modo `dummy-once` (vuelve a leer el archivo cuando cambia su fecha). Estado en `/run/nut/kit.dev` |
| Estado al arrancar | `kit-ups-inicial.service` copia `/etc/nut/kit-inicial.dev` (`OL`) a `/run/nut/kit.dev` antes del driver, así kit01 no se vuelve a apagar al encender después de un apagado con `LB`. Es una unidad propia porque `nut-driver-enumerator` borra los drop-in de `nut-driver@kit` cuando cambia `ups.conf` |
| upsd | Solo en `127.0.0.1:3493` y `[::1]:3493`; no se abre en el firewall |
| upsmon | `primary`, con el usuario `upsmon` y la clave `vault_nut_password` (vault). Avisos al journal (`nut-monitor`) |
| Apagado | `SHUTDOWNCMD` es `/usr/local/sbin/kit-apagado`. Orden y espera en `inventarios/kit/group_vars/all/nut.yml` (`nut_orden_vms: [comunidad01, clinica01]`, `nut_espera_vm: 180`) |
| Monitoreo | `nut-driver@kit`, `nut-server` y `nut-monitor` están en las unidades críticas de node_exporter; si fallan, `UnidadFallida` en **Estado del kit** |

**Cómo apaga `kit-apagado`.** Para cada VM en orden pide el apagado limpio (`virsh shutdown`), que dentro de la VM cierra Docker (PostgreSQL y DHIS2 tienen 60 s, `stop_grace_period` en `apps`) y Samba. Si la VM no termina en 180 s, la fuerza (`virsh destroy`) para que kit01 alcance a apagarse con batería. Después ejecuta `systemctl poweroff`. Cada paso queda en el journal con la etiqueta `kit-apagado`.

## Cómo se despliega

Desde `platform/ansible/`:

```bash
ansible-playbook playbooks/nut.yml
```

Una segunda ejecución termina con `changed=0`. El rol también borra un archivo de simulacro que hubiera quedado.

## Cómo se usa

```bash
sudo kit-ups            # estado de la UPS (ups.status, carga y autonomía)
sudo kit-ups ob         # corte de energía: upsmon avisa, no apaga nada
sudo kit-ups lb         # batería baja: upsmon ejecuta kit-apagado
sudo kit-ups ol         # vuelve la energía
journalctl -t kit-apagado -t kit-ups -u nut-monitor
```

**Simulacro, sin apagar kit01.** Si existe `/etc/kitsalud/nut/simulacro` y tiene menos de una hora, `kit-apagado` apaga las VMs en orden pero no kit01. Al terminar deja la UPS en `OL`, borra el archivo y a los 15 s reinicia NUT para quitar el `FSD`. Las VMs se vuelven a encender con `virsh start` (o solas en el próximo arranque, por el `autostart`).

```bash
sudo touch /etc/kitsalud/nut/simulacro
sudo kit-ups ob; sleep 10; sudo kit-ups lb
```

Un archivo de simulacro con más de una hora no cuenta y el apagado es real. Para probar en el kit real sin ningún riesgo, además se enmascara el apagado mientras dura la prueba, y se desenmascara al terminar (`--runtime` tampoco sobrevive a un reinicio).

```bash
sudo systemctl mask --runtime poweroff.target halt.target     # systemctl poweroff responde "Access denied"
sudo systemctl unmask --runtime poweroff.target halt.target
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `upsc kit@127.0.0.1 ups.status` y `upsc kit@[::1] ups.status` | `OL` |
| `ss -ltn sport = :3493` | Solo `127.0.0.1` y `[::1]` |
| `systemctl is-active kit-ups-inicial nut-driver@kit nut-server nut-monitor` | `active` en las cuatro |
| `sudo kit-ups ob` y `journalctl -u nut-monitor` | `UPS kit@localhost on battery` en unos 5 s, sin apagar nada |
| Simulacro (arriba) | En el journal, `kit-apagado` apaga comunidad01 y después clinica01, y termina con `Simulacro terminado`; `upsc` vuelve a `OL` sin `FSD` |

## Pruebas hechas

| Dónde | Prueba | Resultado |
|---|---|---|
| Laboratorio virtual | Cadena completa (`ob`, `lb`) con dos dominios de prueba sin sistema y 20 s de espera | `ONBATT`, `LB`, `FSD` y `kit-apagado` forzó comunidad01 y después clinica01 y apagó `kitlab-kit01` a los 53 s de `LB`. Al encenderlo volvió en `OL` y no se apagó otra vez |
| Laboratorio virtual | Simulacro vigente y simulacro con el archivo de hace 2 h | El vigente apagó solo las VMs y dejó la UPS en `OL` sin `FSD`, con `upsmon` vigilando. El vencido apagó el host |
| Laboratorio virtual | Instalación desde cero (NUT purgado) | El rol termina sin errores a la primera y la segunda ejecución da `changed=0` |
| kit01 real (2026-11-02) | Simulacro con `poweroff.target` enmascarado | comunidad01 apagada limpia en 2 s y clinica01 en 3 s; PostgreSQL cerró limpio (`database system is shut down` y al volver `was shut down at`, sin recuperación) y Samba sin errores (`dbcheck` con 0 errores). kit01 siguió encendido, con la UPS en `OL`. Al encender las dos VMs a la vez, las 42 sondas quedaron en verde a los 41 s |

El apagado real de kit01 y P12 se hacen en la visita, con alguien en el laboratorio.

## Diagnóstico

- **`upsc` responde `Driver not connected`.** El driver no arrancó. `journalctl -u nut-driver@kit` dice por qué; si es `Can't open /run/nut/kit.dev`, `systemctl start kit-ups-inicial` y `systemctl restart nut-driver@kit`.
- **`upsc` queda en `FSD OL` después de un simulacro.** No corrió el reinicio programado. `sudo systemctl restart nut-driver@kit nut-server nut-monitor`.
- **El simulacro apagó kit01.** El archivo tenía más de una hora o no existía. Por eso las pruebas en el kit real se hacen además con `poweroff.target` enmascarado.
- **Una VM tarda en apagarse.** El journal de `kit-apagado` dice cuántos segundos tardó o si se forzó. Dentro de la VM, `journalctl -b -1` muestra qué servicio demoró el apagado.

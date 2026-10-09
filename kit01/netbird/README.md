# NetBird en kit01

Acceso remoto para administrar el kit durante el desarrollo (D-21, sección 10.7 del documento). No forma parte de la operación en campo.

**Estado (2026-10-09).** Instalado (versión 0.80.0) y conectado. IP de kit01 en la red de NetBird: `100.90.225.113`.

## Instalación

```bash
curl -fsSL https://pkgs.netbird.io/install.sh | sh
 sudo netbird up --setup-key '<SETUP-KEY>'      # con un espacio al inicio: no queda en el historial
```

La clave de registro (setup key) no se versiona: se guarda en `ansible-vault`.

## Uso

```bash
ssh <usuario>@100.90.225.113                                 # kit01
ssh -J <usuario>@100.90.225.113 admin@10.20.10.2             # sw01
ssh -L 8080:10.20.10.3:80 <usuario>@100.90.225.113           # AP: http://localhost:8080
```

## Verificación

```
$ netbird status
Management: Connected
Signal: Connected
NetBird IP: 100.90.225.113/16
```

## Desactivar en campo

```bash
sudo systemctl disable --now netbird
```

## Pendiente (`platform#3`)

- Política en NetBird: solo el grupo de integrantes y solo SSH (TCP 22) hacia kit01.
- Que cada integrante compruebe su acceso desde fuera del laboratorio.

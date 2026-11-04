"""Filtros del rol bind9: nombre de un PTR relativo a su zona inversa y
disparador rpz-client-ip de un prefijo."""
import ipaddress


def nombre_ptr(ip, zona):
    """'10.20.10.1', '20.10.in-addr.arpa' -> '1.10'; funciona igual con IPv6."""
    inverso = ipaddress.ip_address(str(ip)).reverse_pointer
    sufijo = "." + zona.rstrip(".")
    if not inverso.endswith(sufijo):
        raise ValueError(f"{ip} no pertenece a la zona {zona}")
    return inverso[: -len(sufijo)]


def rpz_cliente(prefijo):
    """'10.20.10.0/24' -> '24.0.10.20.10'; 'fd5a:fc7e:d716:10::/64' -> '64.zz.10.d716.fc7e.fd5a'."""
    red = ipaddress.ip_network(str(prefijo))
    if red.version == 4:
        partes = str(red.network_address).split(".")
    else:
        izquierda, _, derecha = red.network_address.compressed.partition("::")
        partes = izquierda.split(":") if izquierda else []
        if _:
            partes += ["zz"] + (derecha.split(":") if derecha else [])
    return ".".join([str(red.prefixlen)] + partes[::-1])


def es_ipv6(ip):
    return ipaddress.ip_address(str(ip)).version == 6


class FilterModule:
    def filters(self):
        return {"nombre_ptr": nombre_ptr, "es_ipv6": es_ipv6, "rpz_cliente": rpz_cliente}

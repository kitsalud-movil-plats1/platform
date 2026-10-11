"""Filtros del rol bind9: nombre de un PTR relativo a su zona inversa."""
import ipaddress


def nombre_ptr(ip, zona):
    """'10.20.10.1', '20.10.in-addr.arpa' -> '1.10'; funciona igual con IPv6."""
    inverso = ipaddress.ip_address(str(ip)).reverse_pointer
    sufijo = "." + zona.rstrip(".")
    if not inverso.endswith(sufijo):
        raise ValueError(f"{ip} no pertenece a la zona {zona}")
    return inverso[: -len(sufijo)]


def es_ipv6(ip):
    return ipaddress.ip_address(str(ip)).version == 6


class FilterModule:
    def filters(self):
        return {"nombre_ptr": nombre_ptr, "es_ipv6": es_ipv6}

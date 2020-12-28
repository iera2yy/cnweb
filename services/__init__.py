from .telnet_connect import TelnetConnect


# 初始化一个连接
def init_connection(host_ip, username, password) -> TelnetConnect:
    tlc = TelnetConnect(host_ip, username, password)
    return tlc


# test
def test():
    return 'this is test init'

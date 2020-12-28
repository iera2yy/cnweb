from flask import Flask, render_template, g, jsonify, make_response
import services

app = Flask(__name__)


# 建立连接
def connect():
    if g.connections and g.connections.length > 0:
        return g.connections
    rta = {'host_ip': '192.168.1.2', 'username': '', 'password': 'CISCO'}
    rtb = {'host_ip': '192.168.1.1', 'username': '', 'password': 'CISCO'}
    rtc = {'host_ip': '10.0.0.2', 'username': '', 'password': 'CISCO'}
    client1 = services.init_connection(rta.get('host_ip'), rta.get('username'), rta.get('password'))
    client2 = services.init_connection(rtb.get('host_ip'), rtb.get('username'), rtb.get('password'))
    client3 = services.init_connection(rtc.get('host_ip'), rtc.get('username'), rtc.get('password'))
    g.connections = [client1, client2, client3]
    return g.connections


def execute_command(clients, idx, commands):
    response = []
    if clients[idx].login_host():
        response = clients[idx].execute_some_command(commands)
        if clients[idx].logout_host():
            g.connections = []
    g.static = True
    return response


# 配置静态NAT
@app.route('/static_nat')
def set_static_nat():
    clients = connect()
    command_a = ['ip subnet-zero',
                 'ip route 0.0.0.0 0.0.0.0 192.168.1.1',
                 'ip route 192.168.1.32 255.255.255.224',
                 'ip route 0.0.0.0 0.0.0.0 10.0.0.1',
                 'ip nat inside source static 10.0.0.2 192.168.1.34',
                 'ip nat inside source static 10.0.0.11 192.168.1.35',
                 'interface e0',
                 'ip nat inside',
                 'interface s0',
                 'ip nat outside']
    print(services.test())
    result = execute_command(clients, 0, command_a)
    return make_response(jsonify(result), 200)


# 删除静态NAT
@app.route('/delete_static_nat')
def delete_static_nat():
    clients = connect()
    command_a = ['no ip nat inside source static 10.0.0.2 192.168.1.34',
                 'no ip nat inside source static 10.0.0.11 192.168.1.35']
    result = execute_command(clients, 0, command_a)
    return make_response(jsonify(result), 200)


# 配置动态NAT
@app.route('/dynamic_nat')
def set_dynamic_nat():
    if g.static:
        return '未删除静态NAT配置'
    clients = connect()
    command_a = ['ip nat pool globalXXYZ 192.168.1.33 192.168.1.57 netmask 255.255.255.224',
                 'access-list 1 permit 10.0.0.0 0.255.255.255',
                 'ip nat inside source list 1 pool globalXYZ overload',
                 'ip http server',
                 'ip nat pool Webservers 10.0.0.1 10.0.0.2 netmask 255.0.0.0 type rotary',
                 'access-list 2 permit host 192.169.1.60',
                 'ip nat inside destination list 2 pool Webservers']
    command_c = ['ip http server']
    result = []
    result.extend(execute_command(clients, 0, command_a))
    result.extend(execute_command(clients, 2, command_c))
    return make_response(jsonify(result), 200)


# 显示NAT转换
@app.route('/show_nat')
def show_nat():
    clients = connect()
    command_a = ['show ip nat translations',
                 'show ip nat translations verbose',
                 'show ip nat statistics']
    result = execute_command(clients, 0, command_a)
    return make_response(jsonify(result), 200)


# 核验配置
@app.route('/show_command')
def show_command():
    clients = connect()
    command_a = ['show running-config',
                 'show ip nat translations']
    result = execute_command(clients, 0, command_a)
    return make_response(jsonify(result), 200)


@app.route('/')
def index():
    return render_template('homepage.html')


if __name__ == '__main__':
    app.run()

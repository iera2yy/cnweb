from flask import Flask, render_template, jsonify, make_response
from flask_cors import CORS
import services

app = Flask(__name__)
CORS(app, supports_credentials=True)


# 建立连接
def connect():
    rta = {'host_ip': '172.16.0.1', 'username': '', 'password': 'CISCO'}
    rtb = {'host_ip': '172.16.0.2', 'username': '', 'password': 'CISCO'}
    rtc = {'host_ip': '172.16.0.3', 'username': '', 'password': 'CISCO'}
    client1 = services.init_connection(rta.get('host_ip'), rta.get('username'), rta.get('password'))
    client2 = services.init_connection(rtb.get('host_ip'), rtb.get('username'), rtb.get('password'))
    client3 = services.init_connection(rtc.get('host_ip'), rtc.get('username'), rtc.get('password'))
    return [client1, client2, client3]


# 断开连接
def disconnect(clients: list):
    for tcl in clients:
        tcl.logout_host()


# 执行命令行
def execute_command(clients, idx, commands):
    response = []
    if clients[idx].login_host():
        response = clients[idx].execute_some_command(commands)
    return response


# 配置路由器信息
@app.route('/router_config')
def config_routers():
    clients = connect()
    command_a = ['conf ter',
                 'int f0/0',
                 'ip address 10.0.0.1 255.0.0.0',
                 'no shutdown',
                 'int s0/0/0',
                 'ip address 192.168.1.2 255.255.255.252',
                 'no shutdown',
                 'end']
    command_b = ['conf ter',
                 'int f0/0',
                 'ip address 192.168.3.1 255.255.255.0',
                 'no shutdown',
                 'int s0/0/0',
                 'ip address 192.168.1.1 255.255.255.252',
                 'no shutdown',
                 'end']
    command_c = ['conf ter',
                 'int f0/0',
                 'ip address 10.0.0.2 255.0.0.0',
                 'no shutdown',
                 'end']
    result = []
    result.extend(execute_command(clients, 0, command_a))
    result.extend(execute_command(clients, 1, command_b))
    result.extend(execute_command(clients, 2, command_c))
    disconnect(clients)
    return make_response(jsonify(result), 200)


# 配置静态NAT
@app.route('/static_nat')
def set_static_nat():
    clients = connect()
    result = []
    # 'ip subnet-zero',
    # RTA
    result.extend(execute_command(clients, 0, ['conf ter', 'ip subnet-zero', 'ip route 0.0.0.0 0.0.0.0 192.168.1.1']))
    # RTB
    result.extend(execute_command(clients, 1, ['conf ter', 'ip route 192.168.1.32 255.255.255.224 192.168.1.2']))
    # RTC
    result.extend(execute_command(clients, 2, ['conf ter', 'ip subnet-zero', 'ip route 0.0.0.0 0.0.0.0 10.0.0.1']))
    command_a = ['conf ter',
                 'ip nat inside source static 10.0.0.2 192.168.1.34',
                 'ip nat inside source static 10.0.0.11 192.168.1.35',
                 'interface f0/0',
                 'ip nat inside',
                 'interface s0/0/0',
                 'ip nat outside']
    # print(services.test())
    result.extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    return make_response(jsonify(result), 200)


# 删除静态NAT
@app.route('/delete_static_nat')
def delete_static_nat():
    clients = connect()
    command_a = ['conf ter',
                 'no ip nat inside source static 10.0.0.2 192.168.1.34',
                 'no ip nat inside source static 10.0.0.11 192.168.1.35',
                 'yes']
    result = execute_command(clients, 0, command_a)
    disconnect(clients)
    return make_response(jsonify(result), 200)


# 配置动态NAT
@app.route('/dynamic_nat')
def set_dynamic_nat():
    clients = connect()
    command_a = ['conf ter',
                 'ip nat pool globalXXYZ 192.168.1.33 192.168.1.57 netmask 255.255.255.224',
                 'access-list 1 permit 10.0.0.0 0.255.255.255',
                 'ip nat inside source list 1 pool globalXYZ overload',
                 'interface f0/0',
                 'ip nat inside',
                 'interface s0/0/0',
                 'ip nat outside']
    result = []
    result.extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    return make_response(jsonify(result), 200)


# 显示NAT转换
@app.route('/show_nat')
def show_nat():
    clients = connect()
    command_a = ['show ip nat translations',
                 'show ip nat translations verbose',
                 'show ip nat statistics']
    result = execute_command(clients, 0, command_a)
    disconnect(clients)
    return make_response(jsonify(result), 200)


# 核验配置
@app.route('/show_config')
def show_command():
    clients = connect()
    command_a = ['show running-config',
                 'show ip nat translations']
    result = execute_command(clients, 0, command_a)
    disconnect(clients)
    return make_response(jsonify(result), 200)


@app.route('/')
def index():
    return render_template('homepage.html')


@app.route('/test')
def test_port():
    result = ['this is a test']
    return make_response(jsonify(result), 200)


if __name__ == '__main__':
    app.run()

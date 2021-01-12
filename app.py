from flask import Flask, render_template, jsonify, make_response, request
from flask_cors import CORS
import services
import json

app = Flask(__name__)
CORS(app, supports_credentials=True)
session = {"state": -1,
           "rta": {"f0/0": "", "s0/0/0": ""},
           "rtb": {"f0/0": "", "s0/0/0": ""},
           "rtc": {"f0/0": "", "s0/0/0": ""}}


# 建立连接
def connect():
    rta = {'host_ip': '172.16.0.1', 'username': 'RTA', 'password': 'CISCO'}
    rtb = {'host_ip': '172.16.0.2', 'username': 'RTB', 'password': 'CISCO'}
    rtc = {'host_ip': '172.16.0.3', 'username': 'RTC', 'password': 'CISCO'}
    client1 = services.init_connection(rta.get('host_ip'), rta.get('username'), rta.get('password'))
    client2 = services.init_connection(rtb.get('host_ip'), rtb.get('username'), rtb.get('password'))
    client3 = services.init_connection(rtc.get('host_ip'), rtc.get('username'), rtc.get('password'))
    return [client1, client2, client3]


# 断开连接
def disconnect(clients: list):
    for tcl in clients:
        if not tcl:
            tcl.logout_host()
            print("%s telnet连接已断开!!!" % tcl.get_hostname())


# 执行命令行
def execute_command(clients, idx, commands):
    response = []
    if clients[idx].login_host():
        response = clients[idx].execute_some_command(commands)
    return response


# 调整输出格式
def format_result(result):
    for i in range(len(result["message"]) - 1):
        if result["message"][i]:
            idx = result["message"][i].rfind('\n')
            result["message"][i + 1] = result["message"][i][idx:] + result["message"][i + 1]
            result["message"][i] = result["message"][i][:idx]
    return result


def format_config(data, rt):
    command = ['conf ter']
    global session
    for item in data:
        command.append("int " + item["port"])
        command.append("ip address " + item["ip"] + " " + item["mask"])
        command.append("no shutdown")
        session[rt][item["port"]] = item["ip"]
    command.append("end")
    return command


def format_static(rt):
    res = ['conf ter', 'ip subnet-zero']
    tmp = 'ip route '
    global session
    if rt == 'rta':
        tmp += '0.0.0.0 0.0.0.0 ' + session[rt]["s0/0/0"]
    elif rt == 'rtb':
        target_ip = session[rt]["s0/0/0"].split('.')
        target_ip[3] = '221'
        target_ip = '.'.join(target_ip)
        mask = '255.255.255.224'
        tmp += target_ip + ' ' + mask + ' ' + session[rt]["s0/0/0"]
    elif rt == 'rtc':
        tmp += '0.0.0.0 0.0.0.0 ' + session[rt]["f0/0"]
    res.append(tmp)
    return res


# 配置路由器信息
@app.route('/router_config', methods=["POST"])
def config_routers():
    # clients = connect()
    data = json.loads(request.get_data(as_text=True))
    data_rta = data["rta"] if "rta" in data.keys() else []
    data_rtb = data["rtb"] if "rtb" in data.keys() else []
    data_rtc = data["rtc"] if "rtc" in data.keys() else []
    command_a = format_config(data_rta, "rta")
    command_b = format_config(data_rtb, "rtb")
    command_c = format_config(data_rtc, "rtc")
    result = {"message": [' '.join(command_a), ' '.join(command_b), ' '.join(command_c)]}
    # result["message"].extend(execute_command(clients, 0, command_a))
    # result["message"].extend(execute_command(clients, 1, command_b))
    # result["message"].extend(execute_command(clients, 2, command_c))
    # disconnect(clients)
    global session
    session["state"] = 0
    return make_response(jsonify(format_result(result)), 200)
    # return make_response(jsonify(result), 200)


# 配置静态NAT
@app.route('/static_nat', methods=["POST"])
def set_static_nat():
    data = json.loads(request.get_data(as_text=True))
    if "staticNat" in data.keys():
        clients = connect()
        data_static = data["staticNat"]
        global session
        result = {"message": []}
        result["message"].extend(execute_command(clients, 0, format_static("rta")))     # RTA
        # print(format_static("rta"))
        result["message"].extend(execute_command(clients, 1, format_static("rtb")))     # RTB
        # print(format_static("rtb"))
        result["message"].extend(execute_command(clients, 2, format_static("rtc")))     # RTC
        # print(format_static("rtc"))
        command_a = [('ip nat inside source static ' + item["from"] + ' ' + item["to"]) for item in data_static]
        command_a = ['conf ter'] + command_a + ['interface f0/0', 'ip nat inside', 'interface s0/0/0', 'ip nat outside']
        result["message"].extend(execute_command(clients, 0, command_a))
        disconnect(clients)
        session["state"] = 1
        # return make_response(jsonify(command_a), 200)
        return make_response(jsonify(format_result(result)), 200)
    else:
        return "静态NAT配置信息不全!"


# 删除静态NAT
@app.route('/delete_static_nat', methods=["POST"])
def delete_static_nat():
    clients = connect()
    command_a = ['conf ter',
                 'no ip nat inside source static 10.0.0.2 192.168.1.34',
                 'no ip nat inside source static 10.0.0.11 192.168.1.35',
                 'yes']
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    global session
    session["state"] = 0
    return make_response(jsonify(format_result(result)), 200)


# 配置动态NAT
@app.route('/dynamic_nat', methods=["POST"])
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
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    global session
    session["state"] = 2
    return make_response(jsonify(format_result(result)), 200)


# 显示NAT转换
@app.route('/show_nat', methods=["POST"])
def show_nat():
    clients = connect()
    command_a = ['show ip nat translations',
                 'show ip nat translations verbose',
                 'show ip nat statistics']
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    print(result)
    disconnect(clients)
    return make_response(jsonify(format_result(result)), 200)


# 核验配置
@app.route('/show_config', methods=["POST"])
def show_command():
    clients = connect()
    command_a = ['show running-config']
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    return make_response(jsonify(format_result(result)), 200)


@app.route('/')
def index():
    return render_template('homepage.html')


@app.route('/test')
def test_port():
    result = ['this is a test']
    return make_response(jsonify(result), 200)


if __name__ == '__main__':
    app.run()

from flask import Flask, render_template, jsonify, make_response, request
from flask_cors import CORS
import services
import json
import re

app = Flask(__name__)

# 开启跨域资源共享
CORS(app, supports_credentials=True)
# 全局变量，存储全局需要的信息
# state: -1未配置；0路由器配置完成；1路由转发协议配置完成；2静态NAT配置完成；4动态NAT配置完成
session = {"state": -1,
           "rta": {"f0/0": "", "s0/0/0": ""},
           "rtb": {"f0/0": "", "s0/0/0": ""},
           "rtc": {"f0/0": "", "s0/0/0": ""},
           "staticNat": [],
           "dynamicNat": {}}
# session = {"state": 1,
#            "rta": {"f0/0": "10.0.0.1", "s0/0/0": "192.168.1.2"},
#            "rtb": {"f0/0": "192.168.3.1", "s0/0/0": "192.168.1.1"},
#            "rtc": {"f0/0": "10.0.0.2", "s0/0/0": ""},
#            "staticNat": [{
#                 "from": "10.0.0.2",
#                 "to": "192.168.1.34"
#             }, {
#                 "from": "10.0.0.11",
#                 "to": "192.168.1.36"
#             }],
#            "dynamicNat": {}}


# 与三台路由器建立telnet连接
def connect():
    rta = {'host_ip': '172.16.0.1', 'username': 'RTA', 'password': 'CISCO'}
    rtb = {'host_ip': '172.16.0.2', 'username': 'RTB', 'password': 'CISCO'}
    rtc = {'host_ip': '172.16.0.3', 'username': 'RTC', 'password': 'CISCO'}
    client1 = services.init_connection(rta.get('host_ip'), rta.get('username'), rta.get('password'))
    if session["state"] == -1:
        execute_command([client1], 0, ["ping 172.16.0.1", "ping 172.16.0.2", "ping 172.16.0.3"])
    client2 = services.init_connection(rtb.get('host_ip'), rtb.get('username'), rtb.get('password'))
    client3 = services.init_connection(rtc.get('host_ip'), rtc.get('username'), rtc.get('password'))
    clients = [client1, client2, client3]
    return clients


# 断开telnet连接
def disconnect(clients: list):
    for tcl in clients:
        if not tcl:
            tcl.logout_host()
            print("%s telnet连接已断开!!!" % tcl.get_hostname())


# 执行命令行，负责向路由器发送指令
def execute_command(clients, idx, commands):
    response = []
    if clients[idx].login_host():
        response = clients[idx].execute_some_command(commands)
    return response


# 格式化输出信息内容
def format_result(result):
    for i in range(len(result["message"]) - 1):
        if result["message"][i]:
            idx = result["message"][i].rfind('\n')
            result["message"][i + 1] = result["message"][i][idx:] + result["message"][i + 1]
            result["message"][i] = result["message"][i][:idx]
    return result


# 格式化配置指令
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


# 格式化路由转发协议指令
def format_static(rt):
    res = ['conf ter', 'ip subnet-zero']
    tmp = 'ip route '
    global session
    if rt == 'rta':
        tmp += '0.0.0.0 0.0.0.0 ' + session["rtb"]["s0/0/0"]
    elif rt == 'rtb':
        target_ip = session["rta"]["s0/0/0"].split('.')
        target_ip[3] = '32'
        target_ip = '.'.join(target_ip)
        mask = '255.255.255.224'
        tmp += target_ip + ' ' + mask + ' ' + session["rta"]["s0/0/0"]
    elif rt == 'rtc':
        tmp += '0.0.0.0 0.0.0.0 ' + session["rta"]["f0/0"]
    res.append(tmp)
    return res


# 配置路由转发协议
def route_protocol(clients):
    res = []
    res.extend(execute_command(clients, 0, format_static("rta")))
    res.extend(execute_command(clients, 1, format_static("rtb")))
    res.extend(execute_command(clients, 2, format_static("rtc")))
    global session
    session["state"] = 1
    return res


# 正则匹配网段，确保前端输入是局域网可用ip
def get_network_segment(ip):
    if re.match(r'^10(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}$', ip):
        return ['10.0.0.0', '0.255.255.255']
    elif re.match(r'^172\.16(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){2}$', ip):
        return ['172.16.0.0', '0.0.255.255']
    elif re.match(r'^192\.168(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){2}$', ip):
        return ['192.168.0.0', '0.0.0.255']
    return None


# 配置路由器信息，包括接口ip、掩码
@app.route('/router_config', methods=["POST"])
def config_routers():
    clients = connect()
    data = json.loads(request.get_data(as_text=True))["config"]
    data_rta = data["rta"] if "rta" in data.keys() else []
    data_rtb = data["rtb"] if "rtb" in data.keys() else []
    data_rtc = data["rtc"] if "rtc" in data.keys() else []
    command_a = format_config(data_rta, "rta")
    command_b = format_config(data_rtb, "rtb")
    command_c = format_config(data_rtc, "rtc")
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    result["message"].extend(execute_command(clients, 1, command_b))
    result["message"].extend(execute_command(clients, 2, command_c))
    disconnect(clients)
    global session
    session["state"] = 0
    return make_response(jsonify(format_result(result)), 200)


# 执行静态NAT配置
@app.route('/static_nat', methods=["POST"])
def set_static_nat():
    data = json.loads(request.get_data(as_text=True))
    if "staticNat" in data.keys():
        clients = connect()
        data_static = data["staticNat"]
        global session
        result = {"message": []}
        result["message"].extend(route_protocol(clients))
        command_a = [('ip nat inside source static ' + item["from"] + ' ' + item["to"]) for item in data_static]
        command_a = ['conf ter'] + command_a + ['interface f0/0', 'ip nat inside', 'interface s0/0/0', 'ip nat outside']
        result["message"].extend(execute_command(clients, 0, command_a))
        disconnect(clients)
        session["state"] = 2
        session["staticNat"] = data_static
        return make_response(jsonify(format_result(result)), 200)
    else:
        return "静态NAT配置信息不全!"


# 删除静态NAT配置
@app.route('/delete_static_nat')
def delete_static_nat():
    global session
    if session["state"] == 2:
        clients = connect()
        command_a = [('no ip nat inside source static ' + item["from"] + ' ' + item["to"])
                     for item in session["staticNat"]]
        command_a = ['conf ter'] + command_a + ['yes']
        result = {"message": []}
        result["message"].extend(execute_command(clients, 0, command_a))
        disconnect(clients)
        session["state"] = 1
        return make_response(jsonify(format_result(result)), 200)
    else:
        return "静态NAT未配置或已删除，无需重复操作!"


# 执行动态NAT配置
@app.route('/dynamic_nat', methods=["POST"])
def set_dynamic_nat():
    global session
    result = {"message": []}
    clients = connect()
    if session["state"] == -1:
        disconnect(clients)
        return "路由未配置!"
    elif session["state"] == 0:
        result["message"].extend(route_protocol(clients))
    elif session["state"] == 2:
        disconnect(clients)
        return "静态NAT未删除!"
    data = json.loads(request.get_data(as_text=True))
    data_dynamic = data["dynamicNat"]
    ip_domain = get_network_segment(session["rta"]["f0/0"])
    if not ip_domain:
        return "配置网段非局域网ip，请重新配置!"
    result["message"].extend(format_static("rta"))
    result["message"].extend(format_static("rtb"))
    result["message"].extend(format_static("rtc"))
    command_a = ['conf ter',
                 'ip nat pool globalXXYZ ' + data_dynamic["from"] +
                 ' ' + data_dynamic["to"] + ' netmask ' + data_dynamic["mask"],
                 'access-list 1 permit ' + ip_domain[0] + ' ' + ip_domain[1],
                 'ip nat inside source list 1 pool globalXYZ overload',
                 'interface f0/0',
                 'ip nat inside',
                 'interface s0/0/0',
                 'ip nat outside']
    result["message"].extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    session["state"] = 4
    session["dynamicNat"] = data_dynamic
    return make_response(jsonify(format_result(result)), 200)


# 显示NAT转换
@app.route('/show_nat', methods=["POST"])
def show_nat():
    clients = connect()
    command_a = ['show ip nat translations']
    result = {"message": []}
    result["message"].extend(execute_command(clients, 0, command_a))
    disconnect(clients)
    return make_response(jsonify(format_result(result)), 200)


# # 核验配置
# @app.route('/show_config', methods=["POST"])
# def show_command():
#     clients = connect()
#     command_a = ['show running-config']
#     result = {"message": []}
#     result["message"].extend(execute_command(clients, 0, command_a))
#     disconnect(clients)
#     return make_response(jsonify(format_result(result)), 200)


@app.route('/verify')
def verification():
    global session
    print(session["state"])
    if session["state"] != 2 and session["state"] != 4:
        return "静态/动态路由均未配置!"
    clients = connect()
    result = {"message": []}
    if session["state"] == 2:
        result["message"].extend(execute_command(clients, 2,
                                                 [('ping ' + item["to"]) for item in session["staticNat"]]))
        for info in result["message"]:
            if not re.search(r'Success rate is ([1-9][0-9]?|100) percent', info):
                return "静态路由配置错误!"
        else:
            result["message"] = ["静态路由配置正确!"]
    elif session["state"] == 4:
        result["message"].extend(execute_command(clients, 0, ['ping ' + session["rtb"]["f0/0"]]))
        for info in result["message"]:
            if not re.search(r'Success rate is ([1-9][0-9]?|100) percent', info):
                return "动态路由配置错误!"
        else:
            result["message"] = ["动态路由配置正确!"]
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

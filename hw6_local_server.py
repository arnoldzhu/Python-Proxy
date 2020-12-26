import asyncio
import struct
import socket
import argparse
import websockets
import logging

username = ''
password = ''
gSendBandwidth = 0
gRecvBandwidth = 0
send_data_len = 0
recv_data_len = 0
remote_host = ''
remote_port = 0

async def client_relay(reader, writer):
    global send_data_len

    while True:
        data = await reader.read(1024)
        if len(data) == 0:
            break
        writer.write(data)
        send_data_len += len(data)
    
    writer.close()

async def serve(reader, writer):
    global username
    global password
    global recv_data_len
    global remote_host
    global remote_port
    data = await reader.read(1)
    
    # SOCKS5 server mode
    if data == b'\x05':
        data = await reader.read(257)       # wait for METHOD package

        writer.write(b'\x05\x00')           # send back METHOD response(X'00')
        await writer.drain()

        data = await reader.read(100)       # wait for CMD package

        # TODO: 解析过程
        addr_type = data[3]                 # get ATYP

        if(addr_type == 1):                 # IPv4 address, DST.ADDR == 4 octets
            ip_addr = socket.inet_ntop(socket.AF_INET, data[4:8])
        elif(addr_type == 3):               # domain name address, DST.ADDR == variable octets
            ip_addr_len = struct.unpack("!B", data[4:5])[0]
            ip_addr = data[5: 5 + ip_addr_len]
        else:                               # IPv6 address, DST.ADDR == 16 octets
            ip_addr = socket.inet_ntop(socket.AF_INET, data[4:4 + 16])
        
        port = struct.unpack("!H", data[-2:])[0]

        # open connection with remote server
        remote_reader, remote_writer = await asyncio.open_connection(host=remote_host, port=remote_port)

        # send self-defined message
        ip_addr = ip_addr.decode()
        port = str(port)
        cmd_request = 'login_info ' + ip_addr + ' ' + port + ' ' + username + ' ' + password + ' SOCKS5'
        cmd_request = cmd_request.encode('utf-8')

        remote_writer.write(cmd_request)           # send CMD package to remote server
        await remote_writer.drain()

        reply = await remote_reader.read(100)   # wait for reply message

        temp = reply.decode()
        temp = temp.split(' ')

        # parse reply packet
        if temp[0] == 'login_successful':
            reply = b'\x05\x00\x00\x01'
            for i in temp[1].split('.'):
                reply += struct.pack('!B', int(i))
            h = int(temp[2])
            reply += struct.pack('!H', h)

            writer.write(reply)                    # send back response
            await writer.drain()

        elif temp[0] == 'password_incorrect':
            print('Password incorrect!')
            remote_reader.close()
            remote_writer.close()

        elif temp[0] == 'username_nonexist':
            print('Username doesn\'t exist!')
            remote_reader.close()
            remote_writer.close()

        else:
            print('Unknown packet format! Connection aborted.')
            remote_reader.close()
            remote_writer.close()

    # HTTP tunnel mode
    elif data == b'C':
        print('lalalahttp')
        temp = await reader.readuntil(b'\r\n\r\n')
        data = data + temp          # concatenate packet back together

        # TODO:解析包
        data = data.decode()		# parse by HTTP format
        b = data.split(' ')
        del data
        ip_addr = b[1].split(':')[0]
        port = b[1].split(':')[1]

        remote_reader, remote_writer = await asyncio.open_connection(host=remote_host, port=remote_port)

        # send self defined message
        http_request = 'login_info ' + ip_addr + ' ' + port + ' ' + username + ' ' + password + ' HTTP'
        http_request = http_request.encode('utf-8')

        remote_writer.write(http_request)
        await remote_writer.drain()

        reply = await remote_reader.read(100)   # wait for reply message
    
        temp = reply.decode()
        temp = temp.split(' ')

        # parse reply packet
        if temp[0] == 'login_successful':
            reply = b'HTTP/1.0 200 Connection established\r\n\r\n'
            writer.write(reply)                    # send back response
            await writer.drain()

        elif temp[0] == 'password_incorrect':
            print('Password incorrect!')
            remote_reader.close()
            remote_writer.close()

        elif temp[0] == 'username_nonexist':
            print('Username doesn\'t exist!')
            remote_reader.close()
            remote_writer.close()

        else:
            print('Unknown packet format! Connection aborted.')
            remote_reader.close()
            remote_writer.close()
    
    # exception mode
    else:
        print('not able to analyze packet header')

    asyncio.create_task(client_relay(reader, remote_writer))  # deal with client data

    while True:                                     # deal with remote server data
        data = await remote_reader.read(1024)
        if len(data) == 0:
            break
        writer.write(data)
        recv_data_len += len(data)
        
    writer.close()

async def localConsole(ws, path):
    global gSendBandwidth
    global gRecvBandwidth
    global send_data_len
    global recv_data_len
    try:
        while True:
            await asyncio.sleep(1)
            msg = await ws.send(f'{gSendBandwidth} {gRecvBandwidth}')
            send_data_len = 0
            recv_data_len = 0
    except websockets.exceptions.ConnectionClosedError as exc:
        logging.error(f'err1{exc}')
    except websockets.exceptions.ConnectionClosedOK as exc:
        logging.error(f'err2{exc}')
    except Exception:
        logging.error(f'err3{traceback.format_exc()}')
        exit(1)

async def calcBandwidth():
    global gSendBandwidth
    global gRecvBandwidth
    global send_data_len
    global recv_data_len

    while True:
        gRecvBandwidth = recv_data_len
        gSendBandwidth = send_data_len
        await asyncio.sleep(1)

async def main():
    global username
    global password
    global remote_host
    global remote_port

    # define command line argument format
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--listenport", help="enter client port", type=str)
    parser.add_argument("-u", "--username", help="enter username to the remote server", type=str)
    parser.add_argument("-w", "--password", help="enter password to the remote server", type=str)
    parser.add_argument("-rh", "--remotehost", help="enter remote host", type=str)
    parser.add_argument("-rp", "--remoteport", help="enter remote port", type=int)

    # get username, password from command line
    args = parser.parse_args()
    username = args.username
    password = args.password
    remote_host = args.remotehost
    remote_port = args.remoteport

    server = await asyncio.start_server(serve, '127.0.0.1', 1080)

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    asyncio.create_task(calcBandwidth())
    ws_server = await websockets.serve(localConsole, '127.0.0.1', 6666)
    asyncio.create_task(calcBandwidth())
    
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
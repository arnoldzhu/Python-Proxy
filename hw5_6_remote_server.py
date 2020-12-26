import asyncio
import struct
import socket
import aiosqlite
import sys
import time

LOGIN_SUCCESS = 1
PASSWORD_INCORRECT = 2
USERNAME_NONEXIST = 3

user_bandwidth = 0

class Token_Bucket(object):

    def __init__(self, rate, capacity):
        self._rate = rate
        self._capacity = capacity
        self._current_amount = capacity
        self._last_consume_time = int(time.time())
    
    async def consume(self, token_amount):
        # calculate token amount added since last consumption
        increment = (int(time.time()) - self._last_consume_time) * self._rate
        # token amount cannot exceed capacity
        self._current_amount = min(increment + self._current_amount, self._capacity)
        
        # if packet amount exceeds current token amount, the packet cannot be sent
        if token_amount > self._current_amount:
            print('exceeding token bucket capacity, unable to send immediately.')
            return False
        # update last time and current token amount
        self._last_consume_time = int(time.time())
        self._current_amount -= token_amount
        return True

async def verify(username, password):
    global user_bandwidth
    async with aiosqlite.connect('proxy_users.db') as db:
        async with db.execute("SELECT * FROM proxy_users") as cursor:
            async for item in cursor:
                if(username == item[0]):
                    if(password == item[1]): 
                        user_bandwidth = item[2]
                        return LOGIN_SUCCESS
                    else:
                        return PASSWORD_INCORRECT
                else:
                    return USERNAME_NONEXIST


async def local_relay(local_reader, external_writer):    
    global user_bandwidth
    controller = Token_Bucket(user_bandwidth, 20480)

    while True:
        data = await local_reader.read(1024)

        if len(data) == 0:
            break

        if await controller.consume(sys.getsizeof(data)):
            external_writer.write(data)
        else:
            pass
    
    external_writer.close()

async def serve(reader, writer):
    global user_bandwidth

    data = await reader.read(100)
    data = data.decode()

    arglist = data.split(' ')

    if arglist[0] == 'login_info':
        result = await verify(arglist[3], arglist[4])

        if result == LOGIN_SUCCESS:
            # 正常情况
            if arglist[5] == 'SOCKS5':

                # SOCKS5 模式
                external_reader, external_writer = await asyncio.open_connection(host=arglist[1], port=arglist[2])

                # 数据库查询成功
                BND_ADDR, BND_PORT = external_writer.get_extra_info("sockname")

                BND_ADDR = str(BND_ADDR)
                BND_PORT = str(BND_PORT)
                reply = 'login_successful ' + BND_ADDR + ' ' + BND_PORT
                
                reply = reply.encode('utf-8')
                writer.write(reply)                    # send back response
                await writer.drain()

            elif arglist[5] == 'HTTP':
                # HTTP 模式
                external_reader, external_writer = await asyncio.open_connection(host=arglist[1], port=int(arglist[2]))

                reply = 'login_successful'
                reply = reply.encode('utf-8')
                writer.write(reply)
                await writer.drain()

            else:
                # 异常模式
                print('Uknown packet format or connection method!')
        
        elif result == PASSWORD_INCORRECT:
            reply = 'password_incorrect'
            reply = reply.encode('utf-8')
            writer.write(reply)
            await writer.drain()

        elif result == USERNAME_NONEXIST:
            reply = 'username_nonexist'
            reply = reply.encode('utf-8')
            writer.write(reply)
            await writer.drain()
    
    else:
        # 异常情况
        print('Unknown packet format!')

    asyncio.create_task(local_relay(reader, external_writer))  # deal with client data

    while True:                                     # deal with external server data
        data = await external_reader.read(1024)
        if len(data) == 0:
            break
        writer.write(data)
        
    writer.close()

async def main():
    server = await asyncio.start_server(serve, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')
    
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
import aiosqlite
import logging
import signal
import asyncio

from sanic import Sanic
from sanic import response
from sanic.response import json
from sanic import exceptions

app = Sanic('RemoteProxyAdmin')
app.config.DB_NAME = 'proxy_users.db'
app.config.DB_USER = 'arnold'

@app.exception(exceptions.NotFound)
async def ignore_404(req, exc):
    return response.text('errUrl', status=404)

@app.get('/get_userinfo')
async def userList(req):
    userList = list()
    async with aiosqlite.connect(app.config.DB_NAME) as db:
        async with db.execute("SELECT username, password, bandwidth FROM proxy_users;") as cursor:
            async for row in cursor:
                user = {'username':row[0], 'password':row[1], 'bandwidth':row[2]}
                logging.debug(f'{user}')
                userList.append(user)
    return response.json(userList)

@app.post('/insert/<userinfo>/<password>/<bandwidth>')
async def userInsert(req, userinfo, password, bandwidth):
    async with aiosqlite.connect(app.config.DB_NAME) as db:
        bandwidth = int(bandwidth)
        await db.execute("INSERT INTO proxy_users VALUES(?, ?, ?)", (userinfo, password, bandwidth, ))
        await db.commit()
    return json({"insert": "complete"})
        
@app.put('/update/<username>/<password>/<bandwidth>')
async def userUpdate(req, username, password, bandwidth):
    async with aiosqlite.connect(app.config.DB_NAME) as db:
        bandwidth = int(bandwidth)
        await db.execute("UPDATE proxy_users SET password = ?, bandwidth = ? WHERE username = ?", (password, bandwidth, username, ))
        await db.commit()
    return json({"update": "complete"})
        
@app.delete('/delete/<username>')
async def userDelete(req, username):
    async with aiosqlite.connect(app.config.DB_NAME) as db:
        await db.execute("DELETE FROM proxy_users WHERE username = ?", (username, ))
        await db.commit()
    return json({"delete": "complete"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
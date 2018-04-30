from datetime import datetime

from aiohttp import web

from users.models import User
from users.serializers import UserSerializer
from utils import views


class UsersView(web.View):
    async def post(self):
        async with self.request.app['db'].acquire() as conn:
            data = await self.request.json()
            u = await conn.execute(User.insert().values(username=data['username'],
                                                        password=data['password'],
                                                        first_name=data['first_name'],
                                                        last_name=data['last_name'],
                                                        role=data['role']))
            res = {}
            async for row in await conn.execute(User.select().where(User.c.id == u.lastrowid)):
                for attr, value in row.items():
                    if type(value) == datetime:
                        value = value.isoformat()
                    res[attr] = value
            return web.json_response(res, status=201)

    async def get(self):
        messages = []
        async with self.request.app['db'].acquire() as conn:
            async for row in conn.execute(User.select()):
                res = {}
                for attr, value in row.items():
                    if type(value) == datetime:
                        value = value.isoformat()
                    res[attr] = value
                messages.append(res)

            return web.json_response(messages)


class UserView(views.DetailView):
    model = User
    serializer_class = UserSerializer
    # queryset = message.c.text == 'Hello'

import asyncio
import aiohttp
from datetime import datetime, timedelta
import logging
import websockets
import names
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK

logging.basicConfig(level=logging.INFO)


async def request(url: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    print(f"Error status: {resp.status} for {url}")
        except aiohttp.ClientConnectorError as err:
            print(f'Connection error: {url}', str(err))


async def get_dates(message: str):
    days = 1
    dates = []

    num_str = ""
    i = len(message) - 1 
    while i >= 0 and message[i].isdigit():
        num_str = message[i] + num_str
        i -= 1

    if num_str:
        days = int(num_str)
        if days >= 10:
            days = 10
       
    for d in range(days):
        result = datetime.now().date() - timedelta(days=d)
        dates.append(result.strftime("%d.%m.%Y"))
    return dates


async def list_urls(message):
    dates = await get_dates(message)
    urls = []
    for date in dates:
        url = f'https://api.privatbank.ua/p24api/exchange_rates?date={date}'
        urls.append(url)
    return urls


async def get_exchange(url):
    result = await request(url)
    if result:
        exc_usd, = list(filter(lambda el: el["currency"] == "USD", result['exchangeRate']))
        exc_eur, = list(filter(lambda el: el["currency"] == "EUR", result['exchangeRate']))
        return f"{url[-10:]} USD Продаж {exc_usd['saleRateNB']}, Покупка {exc_usd['purchaseRateNB']}  EUR Продаж {exc_eur['saleRateNB']}, Покупка {exc_eur['purchaseRateNB']}\n"
    return "Not found"


async def get_exchanges_for_days(message):
    urls = await list_urls(message)
    r = []
    for url in urls:
        r.append(get_exchange(url))
    result = await asyncio.gather(*r)
    return result


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.startswith('exchange'):
                exc = await get_exchanges_for_days(message)
                await self.send_to_clients(exc)
            else:    
                await self.send_to_clients(f"{ws.name}: {message}")


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8020):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    asyncio.run(main())
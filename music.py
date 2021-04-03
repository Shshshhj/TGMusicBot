from pyrogram import Client, filters as f
from pytgcalls import PyTgCalls as Call, StreamType, PyLogs
import asyncio
from func import get_details
import os
import json


app = Client('music')
call = Call(app)
queue = {}
playing = {}
now_playing = {}
ADMIN = [791215137]
PREFIX = ['/', '-', '!', '+', '>', '.', '~']


@app.on_message(f.command(['start', 'help'], PREFIX))
async def start(_, msg):
	chatid = msg.chat.id
	await app.send_message(chatid, f'**Komutlar:** \n`/play <şarkı ismi/youtube linki>` \n`/skip` \n`/volume <ses seviyesi> (çalışmıyor)` \n`/queue` \n`/leave`')


@app.on_message(f.command(['play', 'p'], PREFIX))
async def play(_, msg):
	chatid = msg.chat.id
	global queue
	global playing
	global now_playing

	if not str(chatid) in queue:
		playing[str(chatid)] = False
		queue[str(chatid)] = []
		now_playing[str(chatid)] = ''

    
	details = get_details(msg.text.split(' ', 1)[1])
	vid = details['id']
	vname = details['title']
	thumb = details['thumbnails'][0]
    
	if playing[str(chatid)] == False:
		playing[str(chatid)] = True
		await asyncio.sleep(1)
		now_playing[str(chatid)] = vid
		if os.path.isfile(f'./ses/{vid}.raw') == False:
			os.system(f'ffmpeg -i "$(youtube-dl -x -g "https://youtube.com/watch?v={vid}")" -f s16le -ac 1 -acodec pcm_s16le -ar 48000 ./ses/{vid}.raw')
		await asyncio.sleep(1)
		await msg.reply_text(f'"__{vname}__" oynatiliyor [\u2063]({thumb})')
		call.join_group_call(
			chatid,
			f'./ses/{vid}.raw',
			48000,
			stream_type=StreamType().local_stream
		)
	else:
		queue[str(chatid)].append({'id': vid, 'name': vname, 'thumb': thumb})
		if os.path.isfile(f'./ses/{vid}.raw') == False:
			os.system(f'ffmpeg -i "$(youtube-dl -x -g "https://youtube.com/watch?v={vid}")" -f s16le -ac 1 -acodec pcm_s16le -ar 48000 ./ses/{vid}.raw')
		await msg.reply_text(f'{len(queue[str(chatid)])}. siraya eklendi')



@call.on_stream_end()
async def bitis(chatid):
	global now_playing
	global playing
	global queue

	print(chatid, '-> sarki bitti')
	await asyncio.sleep(2)
	if len(queue[str(chatid)]) > 0:
		call.change_stream(
			chatid,
			f'./ses/{queue[str(chatid)][0]["id"]}.raw'
		)
		await app.send_message(chatid, f'"__{queue[str(chatid)][0]["name"]}__" oynatiliyor [\u2063]({queue[str(chatid)][0]["thumb"]})')
		now_playing[str(chatid)] = queue[str(chatid)][0]["id"]
		queue[str(chatid)].pop(0)
	else:
		playing[str(chatid)] = False
		now_playing[str(chatid)] = ''



@app.on_message(f.command(['skip', 's'], PREFIX))
async def skip(_, msg):
	global now_playing
	global playing
	global queue

	await asyncio.sleep(1)
	if len(queue[str(msg.chat.id)]) > 0:
		call.change_stream(
			msg.chat.id,
			f'./ses/{queue[str(msg.chat.id)][0]["id"]}.raw'
		)
		await app.send_message(msg.chat.id, f'"__{queue[0]["name"]}__" oynatiliyor [\u2063]({queue[0]["thumb"]})')
		now_playing[str(msg.chat.id)] = queue[str(msg.chat.id)][0]["id"]
		queue[str(msg.chat.id)].pop(0)
	else:
		playing[str(msg.chat.id)] = False
		now_playing[str(msg.chat.id)] = ''
		await msg.reply_text('Sirada sarki yok')
		call.leave_group_call(msg.chat.id)
	


@app.on_message(f.command('queue', PREFIX))
async def queue_list(_, msg):
	if len(queue[str(msg.chat.id)]) == 0:
		await msg.reply_text('Sirada sarki yok')
	else:
		text = ''
		i = 0
		while i < len(queue[str(msg.chat.id)]):
			text += f'**{i+1}.** __{queue[str(msg.chat.id)][i]["name"]}__\n'
			i += 1
		await msg.reply_text(text)


@app.on_message(f.command(['volume', 'v'], PREFIX))
async def volume(_, msg):
	vol = int(msg.text.split(' ')[1])
	call.change_volume_call(msg.chat.id, vol)
	await msg.reply_text('Ses seviyesi {} olarak ayarlandi'.format(vol))




@app.on_message(f.command(['leave', 'l'], PREFIX))
async def leave(_, msg):
	global queue
	global playing
	global now_playing

	await msg.reply_text('gidiyom')	
	queue[str(msg.chat.id)] = []
	playing[str(msg.chat.id)] = False
	now_playing[str(msg.chat.id)] = ''

	call.leave_group_call(msg.chat.id)


call.run()

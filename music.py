from pyrogram import Client, filters
from pytgcalls import PyTgCalls, StreamType
import asyncio
from youtube_search import YoutubeSearch
import json
import os
from dotenv import load_dotenv

load_dotenv('config.env')
SESSION = os.environ.get('SESSION', None)
API_ID = int(os.environ.get('API_ID', None))
API_HASH = os.environ.get('API_HASH', None)


LANG = {
	"usage": "**Komutlar:** \n`/play <şarkı ismi/youtube linki>` \n`/skip` \n`/volume <ses seviyesi> (çalışmıyor)` \n`/queue` \n`/leave`",
	"playUsage": "Doğru kullanım: `/play <şarkı ismi/youtube linki>`",
	"volumeUsage": "Doğru kullanım: `/volume <ses seviyesi (0-200)>`",
	"notFound": "`{param}` bulunamadı.",
	"playing": "`{vtitle}` oynatılıyor \nŞarkıyı açan: [{rname}](tg://user?id={rid}) [\u2063]({vthumb})",
	"addedToQueue": "{i}. sıraya eklendi.",
	"leaving": "Sırada şarkı yok. Ayrılıyorum.",
	"leave": "Ayrılıyorum.",
	"anyError": "Bilinmeyen bir hata oluştu: `{error}`",
	"queue": "**Sıradaki şarkılar:**\n{list}",
	"volume": "Ses seviyesi `{vol}` olarak ayarlandı.",
	"queueEmpty": "Sırada şarkı yok.",
	"pause": "Durduruldu.",
	"resume": "Devam ediliyor.",
	"loopOn": "Döngü açıldı.",
	"loopOff": "Döngü kapatıldı."
}

if os.path.isdir('raw_files') == False:
	os.mkdir('raw_files')

MAX_DURATION = 10 #minutes
SUDO = [791215137]
PREFIX = ['/', '-', '!', '+', '>', '.', '~']
GROUPS = {}

"""Functions"""
def get_details(search):
	results = YoutubeSearch(search, max_results=1).to_json()
	results = json.loads(results)
	details = results['videos'][0]
	return details

def markdown_escape(string):
	return string.replace('[', '').replace(']', '').replace('(', '').replace(')', '')

def extract_args(text):
	if ' ' not in text:
		return ''
	else:
		return text.split(' ', 1)[1]


app = Client(SESSION, api_id=API_ID, api_hash=API_HASH)
call = PyTgCalls(app, log_mode=2)

@app.on_message(filters.command('start', PREFIX))
async def start(client, message):
	chatid = message.chat.id
	await client.send_message(chatid, LANG['usage'])
	

@app.on_message(filters.command(['play', 'p'], PREFIX) & filters.group)
async def play(client, message):
	global GROUPS
	chatid = message.chat.id

	if chatid not in GROUPS:
		"""set to default"""
		GROUPS[chatid] = {
			'lang': 'tr',
			'is_playing': False,
			'now_playing': {},
			'loop': False,
			'queue': []
		}
	search_param = extract_args(message.text)
	if search_param == '':
		if message.reply_to_message:
			try:
				details = get_details(message.reply_to_message.text)
			except IndexError:
				return await message.reply_text(LANG['notFound'].format(param=search_param))
	else:
		try:
			details = get_details(search_param)
		except IndexError:
			return await message.reply_text(LANG['notFound'].format(param=search_param))

	requested_by = {'name': message.from_user.first_name, 'id': message.from_user.id}
	vid = details['id']
	vtitle = markdown_escape(details['title'])
	vthumb = details['thumbnails'][0]
	vurl = f'https://youtube.com/watch?v={vid}'

	if os.path.isfile(f'./raw_files/{vid}.raw') == False:
		proc = await asyncio.create_subprocess_shell(
			f'ffmpeg -i "$(youtube-dl -x -g "{vurl}")" -f s16le -ac 1 -acodec pcm_s16le -ar 48000 ./raw_files/{vid}.raw',
			asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
		)
		await proc.communicate()

	if GROUPS[chatid]['is_playing']:
		try:
			GROUPS[chatid]['queue'].append({'id': vid, 'title': vtitle, 'thumb': vthumb, 'requested_by': requested_by})
			await message.reply_text(LANG['addedToQueue'].format(i=len(GROUPS[chatid]['queue'])))
		except Exception as e:
			await message.reply_text(LANG['anyError'].format(error=e))
	else:
		try:
			call.join_group_call(
				chatid,
				f'./raw_files/{vid}.raw',
				stream_type=StreamType().local_stream
			)
			GROUPS[chatid]['is_playing'] = True
			GROUPS[chatid]['now_playing'] = {'title': vtitle, 'id': vid, 'thumb': vthumb, 'requested_by': requested_by}
			await client.send_message(chatid, LANG['playing'].format(vtitle=vtitle, rname=requested_by['name'], rid=requested_by['id'], vthumb=vthumb))
		except Exception as e:
			GROUPS[chatid]['is_playing'] = False
			GROUPS[chatid]['now_playing'] = {}
			await message.reply_text(LANG['anyError'].format(error=e))

@call.on_stream_end()
async def stream_end(chatid):
	global GROUPS

	if GROUPS[chatid]['loop'] == True:
		np = GROUPS[chatid]["now_playing"]
		call.change_stream(
			chatid,
			f'./raw_files/{np["id"]}.raw'
		)
		return await app.send_message(chatid, LANG['playing'].format(vtitle=np['title'], rname=np['requested_by']['name'], rid=np['requested_by']['id'], vthumb=np['thumb']))

	if len(GROUPS[chatid]['queue']) > 0:
		try:
			next_song = GROUPS[chatid]['queue'][0]
			call.change_stream(
				chatid,
				f'./raw_files/{next_song["id"]}.raw'
			)
			GROUPS[chatid]['now_playing'] = next_song
			GROUPS[chatid]['queue'].pop(0)
			await app.send_message(chatid, LANG['playing'].format(vtitle=next_song['title'], rname=next_song['requested_by']['name'], rid=next_song['requested_by']['id'], vthumb=next_song['thumb']))
		except Exception as e:
			await app.send_message(chatid, LANG['anyError'].format(error=e))
	else:
		try:
			call.leave_group_call(
				chatid
			)
			GROUPS[chatid]['queue'] = []
			GROUPS[chatid]['is_playing'] = False
			GROUPS[chatid]['now_playing'] = {}
			await app.send_message(chatid, LANG['leaving'])
		except Exception as e:
			await app.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['skip', 'next', 's', 'n'], PREFIX) & filters.group)
async def skip(client, message):
	global GROUPS
	chatid = message.chat.id

	if GROUPS[chatid]['loop'] == True:
		np = GROUPS[chatid]["now_playing"]
		call.change_stream(
			chatid,
			f'./raw_files/{np["id"]}.raw'
		)
		return await app.send_message(chatid, LANG['playing'].format(vtitle=np['title'], rname=np['requested_by']['name'], rid=np['requested_by']['id'], vthumb=np['thumb']))

	if len(GROUPS[chatid]['queue']) > 0:
		try:
			next_song = GROUPS[chatid]['queue'][0]
			call.change_stream(
				chatid,
				f'./raw_files/{next_song["id"]}.raw'
			)
			GROUPS[chatid]['now_playing'] = next_song
			GROUPS[chatid]['queue'].pop(0)
			await client.send_message(chatid, LANG['playing'].format(vtitle=next_song['title'], rname=next_song['requested_by']['name'], rid=next_song['requested_by']['id'], vthumb=next_song['thumb']))
		except Exception as e:
			await client.send_message(chatid, LANG['anyError'].format(error=e))
	else:
		try:
			call.leave_group_call(
				chatid
			)
			GROUPS[chatid]['queue'] = []
			GROUPS[chatid]['is_playing'] = False
			GROUPS[chatid]['now_playing'] = {}
			await client.send_message(chatid, LANG['leaving'])
		except Exception as e:
			await client.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['leave', 'l'], PREFIX) & filters.group)
async def leave(client, message):
	global GROUPS
	chatid = message.chat.id

	try:
		call.leave_group_call(
			chatid
		)
		GROUPS[chatid]['queue'] = []
		GROUPS[chatid]['is_playing'] = False
		GROUPS[chatid]['now_playing'] = {}
		await client.send_message(chatid, LANG['leave'])
	except Exception as e:
		await client.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['queue'], PREFIX) & filters.group)
async def queue(client, message):
	global GROUPS
	chatid = message.chat.id

	queue = GROUPS[chatid]['queue']
	if len(queue) > 0:
		queue_text = ''
		i = 0
		while i < len(queue):
			queue_text += f"`{i+1}.` **{queue[i]['title']}** ([{queue[i]['requested_by']['name']}](tg://user?id={queue[i]['requested_by']['name']}))\n"
			i += 1
		await message.reply_text(LANG['queue'].format(list=queue_text))
	else:
		await message.reply_text(LANG['queueEmpty'])

@app.on_message(filters.command(['volume', 'vol', 'v'], PREFIX) & filters.group)
async def volume(client, message):
	chatid = message.chat.id
	arg = extract_args(message.text)
	if arg == '':
		return await message.reply_text(LANG['volumeUsage'])
	vol = int(arg) if int(arg) >= 0 and int(arg) <= 200 else 0
	try:
		call.change_volume_call(
			chatid,
			vol
		)
		await message.reply_text(LANG['volume'].format(vol=vol))
	except Exception as e:
		await client.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['pause'], PREFIX) & filters.group)
async def pause(client, message):
	chatid = message.chat.id
	try:
		call.pause_stream(
			chatid
		)
		await message.reply_text(LANG['pause'])
	except Exception as e:
		await client.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['resume'], PREFIX) & filters.group)
async def pause(client, message):
	chatid = message.chat.id
	try:
		call.resume_stream(
			chatid
		)
		await message.reply_text(LANG['resume'])
	except Exception as e:
		await client.send_message(chatid, LANG['anyError'].format(error=e))

@app.on_message(filters.command(['loop'], PREFIX) & filters.group)
async def pause(client, message):
	global GROUPS
	chatid = message.chat.id
	
	if GROUPS[chatid]['loop'] == True:
		GROUPS[chatid]['loop'] = False
		await client.send_message(chatid, LANG['loopOff'])
	elif GROUPS[chatid]['loop'] == False:
		GROUPS[chatid]['loop'] = True
		await client.send_message(chatid, LANG['loopOn'])



call.run()

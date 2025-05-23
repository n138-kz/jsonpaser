import urllib.request
import json
import re
import os
import sys
import math
import discord
import datetime
import time
import logging
import gzip
import shutil
from traceback import print_exc as traceback_print
from zlib import crc32 as calc_crc32
from hashlib import md5 as hash_md5

GITHUB_REPOSITORY = 'n138-kz/jsonpaser'
CONFIG_FILE = '.secret/config.json'

def getVersion(returnable=True,markdown=False):
    version = {}

    f=os.stat(__file__).st_mtime
    v='{0}.{1}.{2}'.format(
        datetime.datetime.fromtimestamp(f).strftime('%Y%m%d'),
        datetime.datetime.fromtimestamp(f).strftime('%H%M%S'),
        hash_md5(str(calc_crc32(str(f).encode('utf-8'))).encode()).hexdigest()[0:8],
    )

    version|={'python':sys.version}
    version|={'discordpy':discord.__version__+' ('+str(discord.version_info)+')'}
    version|={os.path.basename(__file__):v}
    text=''
    for i,v in version.items():
        if markdown:
            text += '{0}\n```\n{1}```\n'.format( i,v )
        else:
            text += '{0}: {1}\n'.format( i,v )

    if returnable:
        return text
    else:
        print(text.replace('`',''))

def default_config():
    config = {}
    config['internal'] = {}
    config['internal']['local'] = {}
    config['internal']['local']['boot_check'] = {}
    config['internal']['local']['boot_check']['directories'] = []
    config['external'] = {}
    config['external']['discord'] = {}
    config['external']['discord']['bot_token'] = ''
    return config

def commit_config(config=default_config(),file=CONFIG_FILE):
    config['internal']['meta'] = {}
    config['internal']['meta']['written_at'] = math.trunc(time.time())
    with open(file, mode='w',encoding='UTF-8') as f:
        json.dump(config, f, indent=4)

def load_config(file=CONFIG_FILE):
    config = default_config()
    if not(os.path.isfile(file)):
        commit_config(config=config,file=file)
    commit_config(file='detail.json')

    with open(file,encoding='UTF-8') as f:
        try:
            config = config | json.load(f)
        except json.decoder.JSONDecodeError as e:
            config = config | default_config()
        commit_config(config=config,file=file)
    return config

def getHTTPResource(url='https://api.github.com/repos/'+GITHUB_REPOSITORY):
    req = urllib.request.Request(
        url=url,
        headers={},
        method='GET',
    )
    response = {
        'body':None,
        'headers':[],
        'code':100,
        'statustext':'',
        'contenttype':'text/plain'
    }
    try:
        with urllib.request.urlopen(req) as res:
            response['code']=res.code
            response['statustext']=res.reason
            response['headers']={}
            for key,value in res.headers.items():
                response['headers'] = response['headers'] | {key:value}
            response['contenttype']=res.headers.get_content_type()
            if re.match(string=response['contenttype'],pattern='^application/json'):
                response['body']=json.load(res)
            else:
                response['body']=None
    except urllib.error.HTTPError as err:
        response['code']=err.code
        response['statustext']=err.reason
    except urllib.error.URLError as err:
        response['code']=err.code
        response['statustext']=err.reason
    return response

def command_help():
    text=''

def boot_checkdir(dirs=[]):
    r={}
    for d in dirs:
        if d[-1]!='/':
            d+='/'
        if os.path.exists(d):
            r = r | {d: True}
        else:
            os.mkdir(d)

def to_gzip(file, delete=False):
    with open(file, 'rb') as f_in:
        with gzip.open(file+'.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    if delete:
        try:
            os.remove(file)
        except FileNotFoundError:
            return f"{file} が見つかりませんでした。"
        except PermissionError:
            return f"{file} を削除する権限がありません。"
        except OSError as e:
            return f"その他のエラーが発生しました: {e}"

config = load_config(file=CONFIG_FILE)
getVersion(returnable=False)
boot_checkdir(config['internal']['local']['boot_check']['directories'])

# Discord APIトークン
DISCORD_API_TOKEN = config['external']['discord']['bot_token']

intents=discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_message_edit(before, after):
    await on_message(after)

@client.event
async def on_message(message):
    # 送信者がbotである場合は弾く
    if message.author.bot:
        return
    
    # テキストチャンネルのみ処理
    if message.channel.type != discord.ChannelType.text:
        return
    
    if message.content.startswith('http://') or message.content.startswith('https://'):
        print(f'on_message: {message.content}')
        print(f'on_guild: {message.guild.id}')
        print(f'on_channel: {message.channel.id}')
        print(f'do_author: {message.author.name}')

        file='log/result_{0}_{1}.json'.format(
            message.author.name,
            math.trunc(time.time()),
        )
        data={
            'meta':{},
            'data':{},
        }
        data['meta']['issue_at']={
            'timestamp':time.time(),
            'timezone': {
                'utc': '{0}'.format(datetime.datetime.now(datetime.timezone.utc)),
                'jst': '{0}'.format(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9),'JST'))),
            }
        }
        data['data']=getHTTPResource(message.content)
        if not(os.path.exists(os.path.dirname(file))):
            os.mkdir(os.path.dirname(file))

        with open('result.json', mode='w', encoding='UTF-8') as f:
            json.dump(data, indent=4, fp=f)
        with open(file, mode='w', encoding='UTF-8') as f:
            json.dump(data, indent=4, fp=f)

        print('meta: '+data['data']['contenttype'])
        print('file: '+file)
        
        if data['data']['body'] is not None:
            embed = discord.Embed(
                title='Result',
                color=0x00ff00,
                url=message.content.split()[0],
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_thumbnail(url=client.user.avatar.url)

            asynclog='log/result_await_{0}.txt'.format(
                math.trunc(time.time()),
            )
            response=await message.reply(embed=embed,files=[discord.File(fp=file,filename='result.json')])
            with open(asynclog, mode='w', encoding='UTF-8', newline='\n') as f:
                f.writelines('{0}'.format(response))
            to_gzip(asynclog,delete=True)
        
        to_gzip(file,delete=True)
@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name='https://...'))
    print('ready.')

file='log/discord.log'
for i in reversed(range(9)):
    if os.path.exists('{0}_{1}.gz'.format(file,i)):
        try:
            os.rename('{0}_{1}.gz'.format(file,i), '{0}_{1}.gz'.format(file,i+1))
        except FileExistsError as e:
            os.remove('{0}_{1}.gz'.format(file,i+1))
            os.rename('{0}_{1}.gz'.format(file,i), '{0}_{1}.gz'.format(file,i+1))

if os.path.exists(file+''):
    with open(file, 'rb') as f_in:
        with gzip.open(file+'_0.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

logging_handler = logging.FileHandler(filename=file+'', encoding='utf-8', mode='w')
try:
    if len(DISCORD_API_TOKEN)>0:
        client.run(DISCORD_API_TOKEN, log_handler=logging_handler, log_level=logging.DEBUG)
    else:
        raise discord.errors.LoginFailure('Token has required.')
except discord.errors.LoginFailure as e:
    timestamp=datetime.datetime.now(datetime.timezone.utc)

    with open('except.log',mode='a',encoding='utf-8',newline='\n') as f:
        f.writelines('{}\n'.format(timestamp))
        traceback_print(file=f)
    traceback_print()
    sys.exit(1)

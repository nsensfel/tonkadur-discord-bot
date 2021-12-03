import discord
import asyncio
import argparse
import socket
import threading
from threading import Lock
import sys
import time

import storyline

################################################################################
## MAIN ########################################################################
################################################################################
parser = argparse.ArgumentParser(
    description = (
        "Discord Client for Tonkadur"
    )
)

parser.add_argument(
    '-t',
    '--token',
    type = str,
    help = 'Discord token.',
)

parser.add_argument(
    '-s',
    '--story',
    type = str,
    help = 'story to test.',
)

args = parser.parse_args()
client = discord.Client()

storylines = []
storyline_indices = dict()

storyline_indices[0] = 0
storylines.append(storyline.Storyline(args.story))

@client.event
async def on_message (message):
    print("message: " + message.clean_content)
    if message.reference is not None:
        output = handle_possible_story_answer(message)
        if (len(output) > 0):
            await message.channel.send(output)
        return

    if i_am_mentioned(message.mentions):
        handle_possible_command(message)
        return
    #await message.channel.send_message(result)

def i_am_mentioned (mentions):
    for mention in mentions:
        if mention.bot and mention.name == "Storyteller":
            return True
    return False

def handle_possible_story_answer (message):
    global storylines
    global storyline_indices

    #msg_id_replied_to = message.reference.message_id
    msg_id_replied_to = 0

    if msg_id_replied_to in storyline_indices:
        storyline_index = storyline_indices[msg_id_replied_to]
        storyline = storylines[storyline_index]
        storyline.handle_answer(
            message.clean_content,
            message.author.name,
            message.author.id
        )
        #storyline.run()

        if (storyline.has_output()):
            return storyline.pop_output_string()

        if (storyline.has_ended()):
            print("The end.")
            return "The end."
        return ""

def handle_possible_command (message):
    print("Was mentioned.")
    return "TODO"

def exit_if_disconnected ():
    while True:
        time.sleep(61)

        if  (client.is_closed):
            print("Timed out.")
            sys.exit()

threading.Thread(target=exit_if_disconnected).start()
client.run(args.token)

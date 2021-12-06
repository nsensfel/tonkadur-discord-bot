import discord
import asyncio
import argparse
import socket
import threading
from threading import Lock
import sys
import time

import narration

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
    help = 'Story to test.',
)

parser.add_argument(
    '-a',
    '--admin',
    type = str,
    nargs='*',
    help = 'Administrators',
)

args = parser.parse_args()
client = discord.Client()

administrators = args.admin

active_narrations_by_post = dict()
active_narrations_by_id = dict()
available_stories = []
orphaned_narrations []
paused_narrations = []

class StoryFile:
    def __init__ (self, filename):
        self.name = "Unnamed Story"
        self.description = "No description."
        self.filename = filename
        self.narrations = []

def get_command_help ():
    return \
"""Tonkadur interface to Discord.
https://github.com/nsensfel/tonkadir-discord-bot

Available commands (global):
- available             Provides a list of available stories.
- active                Provides a list of active narrations.
- paused                Provides a list of paused narrations.
- start INDEX           Starts the story of index INDEX.
- administors           Lists all administrators.
- orphaned              Lists active narrations from deleted/disabled stories.
- narrations_of INDEX   Lists active narrations for story INDEX.

Available commands (narration initiator or admin):
- end INDEX+        Ends the narration of index INDEX
- pause INDEX+      Pauses the narration of index INDEX
- resume INDEX+     Resumes the narration of index INDEX

Available commands (admin):
- add_admin REF+                Adds REF as an admin.
- rm_admin REF+                 Remove REF as an admin.
- add_story STORY_FILE          Adds a new story with file STORY_FILE.
- rm_story_file STORY_FILE      Removes stories and narrations that use this STORY_FILE.
- disable_story INDEX+          Removes story at INDEX (does not remove narrations).
- disable_story_file STORY_FILE Removes stories that use this STORY_FILE (does not remove narrations).
- set_story_name INDEX NAME     Sets name of story at INDEX to NAME.
- set_story_desc INDEX DESC     Sets description of story at INDEX to DESC.
"""

################################################################################
### ADMIN COMMANDS #############################################################
################################################################################
def add_admin (user_id, requester_id):
    global administrators

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    if (user_id in administrators):
        return "This user was already an administrator."

    administrators.append(user_id)

    return "This user is now an administrator."

def rm_admin (user_id, requester):
    global administrators

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    if not (user_id in administrators):
        r
        eturn "This user already not an administrator."

    administrators.remove(user_id)

    return "This user is no longer an administrator."

def add_story (requester_id, story_filename):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    story_file = StoryFile(story_filename)

    available_stories.append(story_file)

    return "Story added (index: " + str(len(available_stories) - 1) + ")."

def rm_story_file (requester_id, story_filename):
    global administrators
    global available_stories
    global active_narrations_by_post
    global active_narrations_by_id
    global orphaned_narrations

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    affected_stories = 0
    affected_narrations = 0
    affected_orphaned_narrations = 0

    i = 0
    limit = list(available_stories)

    result = ""

    while (i < limit):
        story = available_stories[i]

        if (story.filename == story_filename):
            affected_stories += 1
            del available_stories[i]


            for removed_narration in story.narrations:
                affected_narrations += 1
                del active_narrations_by_id[removed_narration.get_id()]

                if (removed_narration.get_is_paused()):
                    paused_narrations.remove(removed_narration)
                else:
                    del active_narrations_by_post[removed_narration.get_last_post_id()]

            result += "Removed story \""
            result += story.name
            result += "\" and its "
            result += str(len(story.narrations))
            result += " narrations.\n"

            limit -= 1
        else:
            i += 1

    i = 0
    limit = list(orphaned_narrations)

    while (i < limit):
        narration = orphaned_narrations[i]

        if (narration.get_story_file().get_filename() == story_filename):
            affected_orphaned_narrations += 1
            del orphaned_narrations[i]
            limit -= 1
        else:
            i += 1

    return (
        result
        + "Story file removed ("
        + str(affected_stories)
        + " stories, "
        + str(affected_narrations)
        + " narrations, and "
        + str(affected_orphaned_narrations)
        + " were affected)."
    )

def disable_story (requester_id, story_index):
    global administrators
    global available_stories
    global orphaned_narrations

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return "Invalid story index."

    deleted_story = available_stories[story_index]

    result = "Disabled story "
    result += deleted_story.name
    result += " ("
    result += deleted_story.filename
    result += ") and orphaned "
    result += str(len(deleted_story.narrations))
    result += " narrations."

    orphaned_narrations.extend(deleted_story.narrations)

    del available_stories[story_index]

    return result

def disable_story_file (requester_id, story_filename):
    global administrators
    global available_stories
    global orphaned_narrations

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    affected_stories = 0

    i = 0
    limit = list(available_stories)

    result = ""

    while (i < limit):
        story = available_stories[i]

        if (story.filename == story_filename):
            affected_stories += 1
            del available_stories[i]

            orphaned_narrations.extend(story.narrations)

            result += "Removed story \""
            result += story.name
            result += "\" and orphaned its "
            result += str(len(story.narrations))
            result += " narrations.\n"

            limit -= 1
        else:
            i += 1

    return (
        result
        + "Story file removed ("
        + str(affected_stories)
        + " stories were affected)."
    )

def set_story_name (requester_id, story_index, name):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return "Invalid story index."

    available_stories[story_index].name = name

    return "Story name set."

def set_story_description (requester_id, story_index, description):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return "Denied. You are not registered as an administrator."

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return "Invalid story index."

    available_stories[story_index].description = description

    return "Story description set."

################################################################################
### GLOBAL COMMANDS ############################################################
################################################################################
def get_story_list ():
    global available_stories

    result = "Available stories:"

    for i in range(len(available_stories)):
        story_file = available_stories[i]
        result += "\n"
        result += str(i)
        result += ". "
        result += story_file.name
        result += "\n"
        result += story_file.filename
        result += "\n"
        result += story_file.description
        result += "\n"

    return result

def get_narration_list ():
    global active_narrations_by_id

    result = "Active narrations:"

    for narration in active_narrations_by_id.values():
        result += "\n"
        result += str(narration.get_id())
        result += ". "
        result += narration.get_story_file().get_name()
        result += "("
        result += narration.get_story_file().get_filename()
        result += ")"
        result += "\n"
        result += "Started by: "
        result += narration.get_initiator_name()
        result += "("
        result += narration.get_initiator_id()
        result += ")"
        result += "\n"

    return result

def remove_narration (user_id, index):
    global administrators
    global active_narrations_by_id
    global active_narrations_by_post

    if not (index in active_narrations_by_id):
        return "There is no narration with this index."

    narration = active_narrations_by_id[index]

    if (
        (user_id != narration.get_initiator_id())
        and not (user_id in administrators)
    ):
        return "Denied. You are not the initiator of this narration nor an administrator."

    del active_narrations_by_id[index]
    del active_narrations_by_post[narration.get_last_post_id()]

    return "Narration " + str(index) + " removed."

def start_story (index, user_id, user_name):
    global available_stories
    global active_narrations_by_id

    if ((index < 0) or (index >= len(available_stories)))
        if (len(available_stories) == 0):
            return "No stories available."
        else:
            return (
                "Choose a story index between 0 and "
                + str(len(available_stories) - 1)
                + "."
            )

    new_story = Narration(available_stories[index], user_id, user_name)
    active_narrations_by_id[new_story.get_id()] = new_story
    new_story.run()

    result = "Narration " + str(new_story.get_id()) + ":\n"
    result += new_story.pop_output()

    return result

################################################################################
### EVENT HANDLING #############################################################
################################################################################
def handle_possible_command (message):
    print("Was mentioned.")
    message_content = message.clean_content.split(" ")

    if (len(message_content) < 2):
        return get_command_help()
    elif (message_content[1] == "available"):
        return get_story_list()
    elif (message_content[1] == "start")
        if (len(message_content) < 3):
            return get_command_help()
        else
            return start_story(int(message_content[2]))
    elif (message_content[1] == "end")
        if (len(message_content) < 3):
            return get_command_help()
        else
            return end_narration(message, int(message_content[2]))

    return get_command_help()

def handle_possible_story_answer (message):
    global active_narrations_by_post

    msg_id_replied_to = message.reference.message_id

    if msg_id_replied_to in active_narrations_by_post:
        narration = active_narrations_by_post[msg_id_replied_to]

        result = "Narration " + str(narration.get_id()) + ":\n"

        narration.handle_answer(
            message.clean_content,
            message.author.name,
            message.author.id
        )

        del active_narrations_by_post[narration.get_last_post_id()]
        narration.update_last_post_id(msg_id_replied_to)
        active_narrations_by_post[msg_id_replied_to] = narration

        if (narration.has_output()):
            result += narration.pop_output_string()

        if (narration.has_ended()):
            result += "\n\nThis narration has now ended."
            del active_narrations_by_id[index]
            del active_narrations_by_post[narration.get_last_post_id()]

        return result

@client.event
async def on_message (message):
    print("message: " + message.clean_content)

    if message.reference is not None:
        output = handle_possible_story_answer(message)

        if (len(output) > 0):
            await message.channel.send(
                content = output,
                reference = message
            )

        return

    if i_am_mentioned(message.mentions):
        output = handle_possible_command(message)

        if (len(output) > 0):
            await message.channel.send(
                content = output,
                reference = message
            )

        return

def i_am_mentioned (mentions):
    for mention in mentions:
        if mention.bot and mention.name == "Storyteller":
            return True
    return False


def exit_if_disconnected ():
    while True:
        time.sleep(61)

        if  (client.is_closed):
            print("Timed out.")
            sys.exit()

threading.Thread(target=exit_if_disconnected).start()
client.run(args.token)

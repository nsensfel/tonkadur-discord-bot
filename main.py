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
    required=True,
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
    '--admins',
    type = str,
    help = 'Administrator tags, space separated.',
)

args = parser.parse_args()

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents = intents)

administrators = dict()
active_narrations_by_post = dict()
active_narrations_by_id = dict()
available_stories = []
orphaned_narrations = []
paused_narrations = []

class StoryFile:
    def __init__ (self, filename):
        self.name = "Unnamed Story"
        self.description = "No description."
        self.filename = filename
        self.narrations = []

    def get_name (self):
        return self.name

    def get_filename (self):
        return self.filename

def get_command_help ():
    return \
"""Tonkadur interface to Discord.
https://github.com/nsensfel/tonkadir-discord-bot

The '+' symbol indicates that the command can be applied to multiple values at
once. This feature is not yet implemented.

Available commands (global):
- available             Provides a list of available stories.
- active                Provides a list of active narrations.
- paused                Provides a list of paused narrations.
- start INDEX           Starts the story of index INDEX.
- administrators           Lists all administrators.
- orphaned              Lists active narrations from deleted/disabled stories.
- narrations_of INDEX   Lists active narrations for story INDEX.

Available commands (narration initiator or admin):
- end INDEX+    Ends the narration of index INDEX
- pause INDEX+  Pauses the narration of index INDEX
- resume INDEX  Resumes the narration of index INDEX

Available commands (admin):
- add_admin TAG+                Adds TAG as an admin.
- rm_admin TAG+                 Remove TAG as an admin.
- add_story_file STORY_FILE     Adds a new story with file STORY_FILE.
- rm_story_file STORY_FILE      Removes stories and narrations that use this STORY_FILE.
- disable_story INDEX+          Removes story at INDEX (does not remove narrations).
- disable_story_file STORY_FILE Removes stories that use this STORY_FILE (does not remove narrations).
- set_story_name INDEX NAME     Sets name of story at INDEX to NAME.
- set_story_desc INDEX DESC     Sets description of story at INDEX to DESC.
"""

################################################################################
### ADMIN COMMANDS #############################################################
################################################################################
def handle_add_admin_command (server, user_tag, requester_name, requester_id):
    global administrators

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    user_data = user_tag.split('#')

    if (len(user_data) != 2):
        return ("Invalid user tag. Use something like nsensfel#0001.", None)

    user = discord.utils.get(
        server.members,
        name = user_data[0],
        discriminator = user_data[1]
    )

    if (user is None):
        return ("Unknown user '" + user_tag + "'.", None)

    if (user.id in administrators):
        return ("This user was already an administrator.", None)

    administrators[user.id] = user_tag

    return (user_tag + " is now an administrator.", None)

def handle_rm_admin_command (server, user_tag, requester_name, requester_id):
    global administrators

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    user_data = user_tag.split('#')

    if (len(user_data) != 2):
        return ("Invalid user tag. Use something like nsensfel#0001.", None)

    user = discord.utils.get(
        server.members,
        name = user_data[0],
        discriminator = user_data[1]
    )

    if (user is None):
        return ("Unknown user '" + user_tag + "'.", None)

    if not (user.id in administrators):
        return ("This user is not an administrator.", None)

    del administrators[user.id]

    return (user_tag + " is no longer an administrator.", None)

def handle_add_story_file_command (story_filename, requester_name, requester_id):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    story_file = StoryFile(story_filename)

    available_stories.append(story_file)

    return (
        ("Story added (index: " + str(len(available_stories) - 1) + ")."),
        None
    )

def handle_rm_story_file_command (story_filename, requester_name, requester_id):
    global administrators
    global available_stories
    global active_narrations_by_post
    global active_narrations_by_id
    global orphaned_narrations

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

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
                delete_narration(removed_narration)

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
        (
            result
            + "Story file removed ("
            + str(affected_stories)
            + " stories, "
            + str(affected_narrations)
            + " narrations, and "
            + str(affected_orphaned_narrations)
            + " were affected)."
        ),
        None
    )

def handle_disable_story_command (story_index, requester_name, requester_id):
    global administrators
    global available_stories
    global orphaned_narrations

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return ("Invalid story index.", None)

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

    return (result, None)

def handle_disable_story_file_command (story_filename, requester_name, requester_id):
    global administrators
    global available_stories
    global orphaned_narrations

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

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
        (
            result
            + "Story file removed ("
            + str(affected_stories)
            + " stories were affected)."
        ),
        None
    )

def handle_set_story_name_command (story_index, name, requester_name, requester_id):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return ("Invalid story index.", None)

    available_stories[story_index].name = name

    return ("Story name set.", None)

def handle_set_story_description_command (story_index, description, requester_name, requester_id):
    global administrators
    global available_stories

    if not (requester_id in administrators):
        return ("Denied. You are not registered as an administrator.", None)

    if ((story_index < 0) or (story_index >= len(available_stories))):
        return ("Invalid story index.", None)

    available_stories[story_index].description = description

    return ("Story description set.", None)

################################################################################
### NARRATION INITIATOR COMMANDS ###############################################
################################################################################
def delete_narration (narration):
    global active_narrations_by_post
    global active_narrations_by_id
    global paused_narrations
    global available_stories

    del active_narrations_by_id[narration.get_id()]

    if (narration.get_is_paused()):
        paused_narrations.remove(narration)
    else:
        del active_narrations_by_post[narration.get_last_post_id()]

    story_filename = narration.get_story_file().filename

    for story in available_stories:
        if (story.filename == story_filename):
            try:
                story.narrations.remove(narration)
            except ValueError: # The narration wasn't found.
                pass # That's not an issue.

    narration.finalize()

def handle_end_narration_command (narration_id, requester_name, requester_id):
    global administrators
    global active_narrations_by_id

    if not (narration_id in active_narrations_by_id):
        return ("There is no narration with this ID.", None)

    narration = active_narrations_by_id[narration_id]

    if (
        (requester_id not in administrators)
        and (narration.get_initiator_id() != requester_id)
    ):
        return (
            "Denied. You are not an administrator or this narration's initiator.",
            None
        )

    delete_narration(narration)

    return ("Narration " + str(narration_id) + " ended.", None)

def handle_pause_narration_command (narration_id, requester_name, requester_id):
    global administrators
    global active_narrations_by_post
    global active_narrations_by_id
    global paused_narrations

    if not (narration_id in active_narrations_by_id):
        return ("There is no narration with this ID.", None)

    narration = active_narrations_by_id[narration_id]

    if (
        (requester_id not in administrators)
        and (narration.get_initiator_id() != requester_id)
    ):
        return (
            "Denied. You are not an administrator or this narration's initiator.",
            None
        )

    if (narration.get_is_paused()):
        return ("This narration is already paused.", None)
    else:
        del active_narrations_by_post[narration.get_last_post_id()]
        paused_narrations.append(narration)
        narration.toggle_is_paused()

        return ("Narration paused", None)

def handle_resume_narration_command (narration_id, requester_name, requester_id):
    global administrators
    global active_narrations_by_post
    global active_narrations_by_id

    if not (narration_id in active_narrations_by_id):
        return ("There is no narration with this ID.", None)

    narration = active_narrations_by_id[narration_id]

    if (
        (requester_id not in administrators)
        and (narration.get_initiator_id() != requester_id)
    ):
        return (
            "Denied. You are not an administrator or this narration's initiator.",
            None
        )

    if (narration.get_is_paused()):
        paused_narrations.remove(narration)
        narration.toggle_is_paused()

        return (narration.get_previous_output(), narration)
    else:
        return ("This narration was not paused.", None)

################################################################################
### GLOBAL COMMANDS ############################################################
################################################################################
def handle_get_story_list_command ():
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

    return (result, None)

def handle_get_active_narration_list_command ():
    global active_narrations_by_id

    result = "Active narrations:"

    for narration in active_narrations_by_id.values():
        result += "\n"
        result += str(narration.get_id())
        result += ". "
        result += narration.get_story_file().get_name()
        result += "("
        result += narration.get_story_file().get_filename()
        result += ")\nStarted by: "
        result += narration.get_initiator_name()
        result += "("
        result += str(narration.get_initiator_id())
        result += ")\n"

        if (narration.get_is_paused()):
            result += "Paused.\n"

    return (result, None)

def handle_get_paused_narration_list_command ():
    global paused_narrations

    result = "Paused narrations:"

    for narration in paused_narrations:
        result += "\n"
        result += str(narration.get_id())
        result += ". "
        result += narration.get_story_file().get_name()
        result += "("
        result += narration.get_story_file().get_filename()
        result += ")\nStarted by: "
        result += narration.get_initiator_name()
        result += "("
        result += str(narration.get_initiator_id())
        result += ")\n"

    return (result, None)

def handle_get_orphaned_narration_list_command ():
    global orphaned_narrations

    result = "Orphaned narrations:"

    for narration in orphaned_narrations:
        result += "\n"
        result += str(narration.get_id())
        result += ". "
        result += narration.get_story_file().get_name()
        result += "("
        result += narration.get_story_file().get_filename()
        result += ")\nStarted by: "
        result += narration.get_initiator_name()
        result += "("
        result += str(narration.get_initiator_id())
        result += ")\n"

        if (narration.get_is_paused()):
            result += "Paused.\n"

    return (result, None)

def handle_get_administrator_list_command ():
    global administrators

    result = "Administrators:"

    for admin_id in administrators:
        result += "\n - "
        result += administrators[admin_id]
        result += " ("
        result += str(admin_id)
        result += ")"

    return (result, None)

def handle_narrations_of_command (index):
    global available_stories

    if ((index < 0) or (index >= len(available_stories))):
        if (len(available_stories) == 0):
            return ("No stories available.", None)
        else:
            return (
                (
                    "Choose a story index between 0 and "
                    + str(len(available_stories) - 1)
                    + "."
                ),
                None
            )

    result = "Narrations for this story:"

    for narration in available_stories[index].narrations:
        result += "\n"
        result += str(narration.get_id())
        result += ". "
        result += narration.get_story_file().get_name()
        result += "("
        result += narration.get_story_file().get_filename()
        result += ")\nStarted by: "
        result += narration.get_initiator_name()
        result += "("
        result += str(narration.get_initiator_id())
        result += ").\n"

        if (narration.get_is_paused()):
            result += "Paused.\n"

    return (result, None)

def handle_start_narration_command (index, requester_name, requester_id):
    global available_stories
    global active_narrations_by_id

    if ((index < 0) or (index >= len(available_stories))):
        if (len(available_stories) == 0):
            return ("No stories available.", None)
        else:
            return (
                (
                    "Choose a story index between 0 and "
                    + str(len(available_stories) - 1)
                    + "."
                ),
                None
            )

    new_narration = narration.Narration(
        available_stories[index],
        requester_name,
        requester_id
    )
    active_narrations_by_id[new_narration.get_id()] = new_narration
    new_narration.run(requester_name, requester_id)

    return (new_narration.pop_output_string(), new_narration)

################################################################################
### EVENT HANDLING #############################################################
################################################################################

def handle_possible_command (message):
    print("Was mentioned.")

    message_content = message.clean_content.split(' ')

    if (len(message_content) < 2):
        return (get_command_help(), None)

    #### GLOBAL COMMANDS
    elif (message_content[1] == "available"):
        return handle_get_story_list_command()

    elif (message_content[1] == "active"):
        return handle_get_active_narration_list_command()

    elif (message_content[1] == "paused"):
        return handle_get_paused_narration_list_command()

    elif (message_content[1] == "start"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_start_narration_command(
                int(message_content[2]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "administrators"):
        return handle_get_administrator_list_command()

    elif (message_content[1] == "orphaned"):
        return handle_get_orphaned_narration_list_command()

    elif (message_content[1] == "narrations_of"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_narrations_of_command(int(message_content[2]))

    #### NARRATION INITIATOR COMMANDS
    elif (message_content[1] == "end"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_end_narration_command(
                int(message_content[2]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "pause"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_pause_narration_command(
                int(message_content[2]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "resume"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_resume_narration_command(
                int(message_content[2]),
                message.author.display_name,
                message.author.id
            )

    #### ADMINISTRATOR COMMANDS
    elif (message_content[1] == "add_admin"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_add_admin_command(
                message.guild,
                message_content[2],
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "rm_admin"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_rm_admin_command(
                message.guild,
                message_content[2],
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "add_story_file"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_add_story_file_command(
                " ".join(message_content[2:]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "rm_story_file"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_rm_story_file_command(
                " ".join(message_content[2:]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "disable_story"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_disable_story_command(
                int(message_content[2]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "disable_story_file"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_disable_story_file_command(
                " ".join(message_content[2:]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "set_story_name"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_set_story_name_command(
                int(message_content[2]),
                " ".join(message_content[3:]),
                message.author.display_name,
                message.author.id
            )

    elif (message_content[1] == "set_story_desc"):
        if (len(message_content) < 3):
            return (get_command_help(), None)
        else:
            return handle_set_story_description_command(
                int(message_content[2]),
                " ".join(message_content[3:]),
                message.author.display_name,
                message.author.id
            )

    return (get_command_help(), None)

def handle_possible_story_answer (message):
    global active_narrations_by_post

    msg_id_replied_to = message.reference.message_id

    if msg_id_replied_to in active_narrations_by_post:
        narration = active_narrations_by_post[msg_id_replied_to]

        result = ""

        narration.handle_answer(
            message.clean_content,
            message.author.display_name,
            message.author.id
        )

#        del active_narrations_by_post[narration.get_last_post_id()]
#        narration.update_last_post_id(msg_id_replied_to)
#        active_narrations_by_post[msg_id_replied_to] = narration

        if (narration.has_output()):
            result += narration.pop_output_string()

        if (narration.has_ended()):
            result += "\n\nThis narration has now ended."
            delete_narration(narration)
            narration = None

        return (result, narration)

    return ("", None)

def replace_narration_post_id (narration, new_post_id):
    global active_narrations_by_post

    if (narration.get_is_paused()):
        return

    if (narration.get_last_post_id() is not None):
        del active_narrations_by_post[narration.get_last_post_id()]

    narration.set_last_post_id(new_post_id)

    active_narrations_by_post[new_post_id] = narration


@client.event
async def on_message (message):
    print("message: " + message.clean_content)

    if message.reference is not None:
        (output, maybe_narration) = handle_possible_story_answer(message)

        if (len(output) > 0):
            if (maybe_narration is not None):
                output += "\n\nReply to this message to continue the narration."

            sent_message = await message.channel.send(
                content = output,
                reference = message
            )

            if (maybe_narration is not None):
                replace_narration_post_id(
                    maybe_narration,
                    sent_message.id
                )

        return

    if i_am_mentioned(message.mentions):
        (output, maybe_narration) = handle_possible_command(message)

        if (len(output) > 0):
            if (maybe_narration is not None):
                output += "\n\nReply to this message to continue the narration."

            sent_message = await message.channel.send(
                content = output,
                reference = message
            )

            if (maybe_narration is not None):
                replace_narration_post_id(
                    maybe_narration,
                    sent_message.id
                )

        return

def i_am_mentioned (mentions):
    for mention in mentions:
        if mention.bot and mention.name == "Storyteller":
            return True

    return False

@client.event
async def on_ready ():
    global args

    for admin in args.admins.split(' '):
        user_data = admin.split('#')

        if (len(user_data) != 2):
            print("Invalid user tag for admins. Use something like nsensfel#0001.")
            continue

        user = discord.utils.get(
            client.users,
            name = user_data[0],
            discriminator = user_data[1]
        )

        if (user is None):
            print("Unknown user '" + admin + "' could not be added as admin.")
            continue

        administrators[user.id] = admin

    args.admins = []

client.run(args.token)

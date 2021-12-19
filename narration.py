import tonkadur

class Narration:
    NOT_STARTED = -1
    WANTS_INT = 0
    WANTS_STR = 1
    WANTS_USER_CHOICE = 2
    IS_RUNNING = 3
    HAS_ENDED = 4

    id_generator = 0
    free_ids = []

    def __init__ (self, story_file, initiator_name, initiator_id):
        self.status = Narration.NOT_STARTED
        self.state = tonkadur.Tonkadur(
            story_file.filename,
            initiator_name,
            initiator_id
        )
        self.is_paused = False
        self.initiator_name = initiator_name
        self.initiator_id = initiator_id
        self.next_input_min = 0
        self.next_input_max = 0
        self.text_options = []
        self.event_options = []
        self.output = ""
        self.previous_output = ""
        self.story_file = story_file
        self.last_post_id = None

        if (len(Narration.free_ids) > 0):
            self.id = Narration.free_ids[0]
            del Narration.free_ids[0]
        else:
            self.id = Narration.id_generator
            Narration.id_generator += 1

    def get_id (self):
        return self.id

    def get_initiator_name (self):
        return self.initiator_name

    def get_initiator_id (self):
        return self.initiator_id

    def reset_next_input (self):
        self.next_input_type = None
        self.next_input_min = 0
        self.next_input_max = 0
        self.text_options = []
        self.event_options = []

    def handle_int_input (self, text, actor_name, actor_id):
        user_input = int(text)
        if (
            (user_input >= self.next_input_min)
            and (user_input <= self.next_input_max)
        ):
            self.state.store_integer(user_input, actor_name, actor_id)
            self.status = Narration.IS_RUNNING
            self.run(actor_name, actor_id)
        else:
            self.display_string(
                "Integer should be within ["
                + str(self.next_input_min)
                + ", "
                + str(self.next_input_max)
                + "] range."
            )

    def handle_str_input (self, text, actor_name, actor_id):
        if (
            (len(text) >= self.next_input_min)
            and (len(text) <= self.next_input_max)
        ):
            self.status = Narration.IS_RUNNING
            self.state.store_string(text, actor_name, actor_id)
            self.run(actor_name, actor_id)
        else:
            self.display_string(
                "String size should be within ["
                + str(self.next_input_min)
                + ", "
                + str(self.next_input_max)
                + "] range."
            )

    def finalize (self):
        Narration.free_ids.append(self.id)

    def handle_option_input (self, text, actor_name, actor_id):
        user_input = int(text)

        if (user_input < 0) or (user_input >= len(self.text_options)):
            self.display_string(
                "Invalid choice. Number between 0 and "
                + str(len(self.text_options) -1)
                + " expected."
            )
            return

        self.status = Narration.IS_RUNNING
        self.state.resolve_choice_to(self.text_options[user_input], actor_name, actor_id)
        self.run(actor_name, actor_id)

    def handle_answer (self, text, actor_name, actor_id):
        if self.status == Narration.NOT_STARTED:
            self.run(actor_name, actor_id)
        elif self.status == Narration.WANTS_INT:
            self.handle_int_input(text, actor_name, actor_id)
        elif self.status == Narration.WANTS_STR:
            return self.handle_str_input(text, actor_name, actor_id)
        elif self.status == Narration.WANTS_USER_CHOICE:
            return self.handle_option_input(text, actor_name, actor_id)
        else:
            self.display_string("No input expected at this point.")

    def handle_event_input (self, event_name, event_data, actor_name, actor_id):
        if not (self.status == Narration.WANTS_USER_CHOICE):
            print(
                "[W] Ignoring event \""
                + str(event_name)
                + "\" from "
                + str(actor_name)
                + " ("
                + str(actor_id)
                + "): not expecting a player choice."
            )
            return

        #for (expected_event_name, expected_event_data, option_id) in self.event_options:
        #    if (
        #        (expected_event_name == event_name)
        #        and (expected_event_data == event_data)
        #    ):
        # TODO: Event support.

    def text_to_string (text):
        str_content = ""

        if (not (text['effect'] is None)):
            str_content += "{(" + str(text['effect']) + ") "

        for c in text['content']:
            if (isinstance(c, str)):
                str_content += c
            else:
                str_content += Narration.text_to_string(c)

        if (not (text['effect'] is None)):
            str_content += "}"

        return str_content


    def display_text (self, text):
        self.display_string(Narration.text_to_string(text))

    def display_string (self, string):
        self.output += string

    def pop_output_string (self):
        self.previous_output = self.output
        self.output = ""

        return self.previous_output

    def get_previous_output (self):
        return self.previous_output

    def get_is_paused (self):
        return self.is_paused

    def toggle_is_paused (self):
        self.is_paused = not self.is_paused

        if (self.is_paused):
            self.last_post_id = None

    def get_story_file (self):
        return self.story_file

    def get_last_post_id (self):
        return self.last_post_id

    def set_last_post_id (self, post_id):
        self.last_post_id = post_id

    def has_output (self):
        return (len(self.output) > 0)

    def has_ended (self):
        return (self.status == Narration.HAS_ENDED)

    def run (self, actor_name, actor_id):
        result = self.state.run(actor_name, actor_id)
        result_category = result['category']

        if (self.status == Narration.NOT_STARTED):
            self.status = Narration.IS_RUNNING

        if (result_category == "end"):
            self.status = Narration.HAS_ENDED
        elif (result_category == "display"):
            self.display_text(result['content'])
            self.run(actor_name, actor_id)
        elif (result_category == "prompt_integer"):
            self.reset_next_input()
            self.status = Narration.WANTS_INT
            self.next_input_min = result['min']
            self.next_input_max = result['max']
            self.display_text(result['label'])
            self.display_string(
                "\n(an integer between "
                + str(result['min'])
                + " and "
                + str(result['max'])
                + " is expected)\n"
            )
        elif (result_category == "prompt_string"):
            self.reset_next_input()
            self.status = Narration.WANTS_STR
            self.next_input_min = result['min']
            self.next_input_max = result['max']
            self.display_text(result['label'])
            self.display_string(
                "\n(a string of size between "
                + str(result['min'])
                + " and "
                + str(result['max'])
                + " is expected)\n"
            )
        elif (result_category == "assert"):
            print(
                "Assert failed at line "
                + str(result['line'])
                + ":"
                + str(result['message'])
            )
            print(str(state.memory))
            self.display_string(
                "\nAssert failed at line "
                + str(result['line'])
                + ": "
            )
            self.display_text(result['message'])
            self.display_string(
                "\nState of memory:\n"
                + str(state.memory)
            )
            self.run(actor_name, actor_id)
        elif (result_category == "resolve_choice"):
            self.reset_next_input()
            self.status = Narration.WANTS_USER_CHOICE
            current_choice = 0

            self.display_string("\n")

            for choice in result['options']:
                if (choice["category"] == "text_option"):
                    self.display_string(str(current_choice) + ": ")
                    self.display_text(choice['label'])
                    self.display_string("\n")
                    self.text_options.append(current_choice);
                else:
                    # TODO: handle events.
                    self.event_options.append(current_choice)
                current_choice += 1

